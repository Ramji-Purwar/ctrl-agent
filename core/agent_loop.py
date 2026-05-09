import json
import logging
from config.settings import BASE_DIR
from core.api_pool import call_llm
from tools.registry import TOOL_REGISTRY, TOOL_SCHEMAS
from core.memory import load_history, save_history

MAX_TOOL_ITERATIONS = 15
MAX_FORMAT_RETRIES  = 3

SYSTEM_PROMPT = (
    "You are a helpful personal assistant and local file system agent running on Windows. "
    "You can answer general questions and also use tools to manage files and folders. "
    f"The user's base directory is: {BASE_DIR}. "
    "STRICT RULES — follow these every time: "
    "1. Never guess a full path. If you don't know the exact path, call find_folder or find_file first. "
    "2. For open_folder: always call find_folder first unless the user gave a full path explicitly. "
    "3. For make_folder inside X: always call find_folder to locate X, then make the folder inside the result. "
    "4. For find_file: return the location only. Do NOT call read_file unless the user asked to read the file. "
    "5. To call a tool, use the native tool_calls mechanism only — never write <function=...> in text. "
    "6. Call one tool at a time. Wait for its result before calling the next tool. Never nest tool calls. "
)

_MALFORMED_PATTERNS = ["<function=", "<function ", "</function>"]

def _is_malformed(text: str) -> bool:
    return any(p in text for p in _MALFORMED_PATTERNS)

_FORMAT_REMINDER = (
    "Your last tool call was malformed or rejected by the API. "
    "Rules: (1) Use ONLY the native tool_calls mechanism. "
    "(2) Never write <function=...> syntax in text. "
    "(3) Call one tool at a time — never nest calls. "
    "Try the same task again using proper tool_calls."
)

def run_agent(user_message: str) -> dict:
    history    = load_history()
    history.append({"role": "user", "content": user_message})
    tools_used     = []
    format_retries = 0  # single shared counter for all format/rejection errors

    for iteration in range(MAX_TOOL_ITERATIONS):

        # LLM call
        try:
            response = call_llm(
                [{"role": "system", "content": SYSTEM_PROMPT}] + history,
                tools=TOOL_SCHEMAS
            )
        except Exception as e:
            err = str(e)
            is_format_error = (
                "tool_use_failed"          in err or
                "Failed to call a function" in err or
                "tool call validation failed" in err
            )
            if is_format_error and format_retries < MAX_FORMAT_RETRIES:
                format_retries += 1
                logging.warning(
                    f"[Agent][Iter {iteration}] API-level tool format error "
                    f"(retry {format_retries}/{MAX_FORMAT_RETRIES})"
                )
                history.append({"role": "user", "content": _FORMAT_REMINDER})
                continue

            logging.error(f"[Agent][Iter {iteration}] LLM call failed: {e}")
            return {"response": f"API error: {e}. Try again in a moment.",
                    "tools_used": tools_used, "success": False}

        # Parse response
        message       = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if not message:
            logging.warning(f"[Agent][Iter {iteration}] Empty message returned.")
            return {"response": "The model returned an empty response. Try rephrasing.",
                    "tools_used": tools_used, "success": False}

        if finish_reason == "stop" or not message.tool_calls:
            final_text = message.content or ""

            if _is_malformed(final_text):
                if format_retries < MAX_FORMAT_RETRIES:
                    format_retries += 1
                    logging.warning(
                        f"[Agent][Iter {iteration}] Malformed tool call in text "
                        f"(retry {format_retries}/{MAX_FORMAT_RETRIES})"
                    )
                    history.append({"role": "user", "content": _FORMAT_REMINDER})
                    continue
                else:
                    logging.error(f"[Agent][Iter {iteration}] Malformed tool call persists — giving up.")
                    return {"response": "I had trouble calling the right tool. Try rephrasing.",
                            "tools_used": tools_used, "success": False}

            history.append({"role": "assistant", "content": final_text})
            save_history(history)
            return {"response": final_text, "tools_used": tools_used, "success": True}

        # Tool calls
        history.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ]
        })

        for tc in message.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Bad args: {tc.function.arguments}")
                tool_args = {}

            logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Args: {tool_args}")
            tools_used.append(tool_name)

            tool_fn = TOOL_REGISTRY.get(tool_name)
            result  = tool_fn(**tool_args) if tool_fn else {"success": False, "error": f"Tool not found: {tool_name}"}

            if not result.get("success", False):
                logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Failed: {result.get('error')}")
                tool_result_content = f"Tool failed with error: {result.get('error', 'Unknown error')}"
            else:
                logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Success")
                tool_result_content = json.dumps(result)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result_content,
            })

        format_retries = 0 

    save_history(history)
    return {"response": "Reached max iterations. Try breaking your request into smaller steps.",
            "tools_used": tools_used, "success": False}