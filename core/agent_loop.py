import json
import logging
from config.settings import BASE_DIR
from core.api_pool import call_llm
from tools.registry import TOOL_REGISTRY, TOOL_SCHEMAS
from core.memory import load_history, save_history

MAX_TOOL_ITERATIONS = 15

SYSTEM_PROMPT = (
    "You are a helpful personal assistant and local file system agent running on Windows. "
    "You can answer general questions and also use tools to manage files and folders. "
    f"The user's base directory is: {BASE_DIR}. "
    "When calling find_file or list_directory, always pass search_root explicitly based on "
    "what the user says. Examples: "
    "'find X on desktop' -> search_root = 'C:\\\\Users\\\\r4849\\\\Desktop'. "
    "If the user gives no location, use BASE_DIR as search_root. "
    "When a tool returns file content, always display the full content verbatim. "
    "IMPORTANT: To call a tool, you MUST use the native tool_calls mechanism only. "
    "NEVER write tool calls as plain text or in any <function=...> format in your response. "
    "If you are unsure of a path, use list_directory or find_file to discover it first. "
    "Never guess a full path — always verify with a tool first if you are not certain."
)

# Patterns that indicate the model tried to call a tool as plain text
_MALFORMED_TOOL_PATTERNS = [
    "<function=",
    "<function ",
    "</function>",
]


def _is_malformed_tool_call(text: str) -> bool:
    return any(pattern in text for pattern in _MALFORMED_TOOL_PATTERNS)


def run_agent(user_message: str) -> dict:
    history = load_history()
    history.append({"role": "user", "content": user_message})
    tools_used = []
    malformed_retries = 0
    MAX_MALFORMED_RETRIES = 2

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            messages_with_system = [{"role": "system", "content": SYSTEM_PROMPT}] + history
            response = call_llm(messages_with_system, tools=TOOL_SCHEMAS)
        except Exception as e:
            logging.error(f"[Agent][Iter {iteration}] LLM call failed: {e}")
            return {
                "response": f"API error: {e}. Try again in a moment.",
                "tools_used": tools_used,
                "success": False
            }

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Guard against empty response
        if not message:
            logging.warning(f"[Agent][Iter {iteration}] Empty message returned.")
            return {
                "response": "The model returned an empty response. Try rephrasing.",
                "tools_used": tools_used,
                "success": False
            }

        # Final answer — no tool calls
        if finish_reason == "stop" or not message.tool_calls:
            final_text = message.content or ""

            # Detect if the model tried to call a tool as plain text (malformed)
            if _is_malformed_tool_call(final_text):
                if malformed_retries < MAX_MALFORMED_RETRIES:
                    malformed_retries += 1
                    logging.warning(
                        f"[Agent][Iter {iteration}] Malformed tool call detected in text "
                        f"(retry {malformed_retries}/{MAX_MALFORMED_RETRIES}) — injecting format reminder"
                    )
                    history.append({
                        "role": "user",
                        "content": (
                            "You tried to call a tool but used the wrong format. "
                            "Do NOT write <function=...> or any tool call syntax in your text. "
                            "You MUST use the native tool_calls mechanism — it is available to you. "
                            "Please try again using tool_calls."
                        )
                    })
                    continue  # retry the iteration
                else:
                    # Retries exhausted — strip the broken text and return a clean error
                    logging.error(
                        f"[Agent][Iter {iteration}] Malformed tool call persists after "
                        f"{MAX_MALFORMED_RETRIES} retries — giving up."
                    )
                    return {
                        "response": "Sorry, I had trouble calling the right tool for this. Try rephrasing your request.",
                        "tools_used": tools_used,
                        "success": False
                    }

            history.append({"role": "assistant", "content": final_text})
            save_history(history)
            return {
                "response": final_text,
                "tools_used": tools_used,
                "success": True
            }

        # Has tool calls — process all of them
        # Append assistant message with tool_calls
        history.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in message.tool_calls
            ]
        })

        for tc in message.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Failed to parse args: {tc.function.arguments}")
                tool_args = {}

            logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Args: {tool_args}")
            tools_used.append(tool_name)

            tool_fn = TOOL_REGISTRY.get(tool_name)
            if tool_fn:
                result = tool_fn(**tool_args)
            else:
                result = {"success": False, "error": f"Tool not found: {tool_name}"}

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Failed: {error_msg}")
                tool_result_content = f"Tool failed with error: {error_msg}"
            else:
                logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Success")
                tool_result_content = json.dumps(result)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result_content,
            })

        # Reset malformed retry counter after a successful real tool call cycle
        malformed_retries = 0

    save_history(history)
    return {
        "response": "Reached max iterations. Try breaking your request into smaller steps.",
        "tools_used": tools_used,
        "success": False
    }