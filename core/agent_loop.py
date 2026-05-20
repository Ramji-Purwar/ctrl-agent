import json
import logging
import re
from config.settings import GIT_USERNAME, get_base_dir
from core.api_pool import call_llm
from tools.registry import TOOL_REGISTRY, TOOL_SCHEMAS
from core.memory import load_history, save_history

MAX_TOOL_ITERATIONS = 15
MAX_FORMAT_RETRIES  = 3

def _build_system_prompt() -> str:
    github_context = (
        f"The user's GitHub username is: {GIT_USERNAME}. "
        if GIT_USERNAME else
        "The user's GitHub username is not configured. "
    )

    return (
        "You are a helpful personal assistant and local file system agent running on Windows. "
        "You can answer general questions and also use tools to manage files and folders. "
        f"The user's base directory is: {get_base_dir()}. "
        f"{github_context}"
        "STRICT RULES — follow these every time: "
        "1. Never guess a full path. If you don't know the exact path, call find_folder or find_file first. "
        "2. For open_folder: always call find_folder first unless the user gave a full path explicitly. "
        "3. For make_folder inside X: always call find_folder to locate X, then make the folder inside the result. "
        "4. For find_file: return the location only. Do NOT call read_file unless the user asked to read the file. "
        "5. To call a tool, use the native tool_calls mechanism only — never write <function=...> in text. "
        "6. Call one tool at a time. Wait for its result before calling the next tool. Never nest tool calls. "
        "7. For git_push: always call git_push_dry_run first, show the user the preview, and wait for their "
        "   explicit confirmation before calling git_push with confirmed=true. "
        "8. When a tool returns requires_confirmation=true, relay the confirmation message to the user and wait. "
        "   Do NOT call the tool again until the user explicitly says to proceed. "
        "9. Never read or reveal secret files such as .env files, API keys, tokens, or credentials. "
        "10. If the user asks to clone '<repo-name>' or says the repo is from 'my GitHub', and a GitHub "
        "    username is configured, use https://github.com/<configured-username>/<repo-name>.git. "
        "    If no GitHub username is configured, ask for the username instead of guessing."
    )

_MALFORMED_PATTERNS = ["<function=", "<function ", "</function>"]
_MALFORMED_TOOL_RE = re.compile(
    r"<function=([A-Za-z_][A-Za-z0-9_]*)\((\{.*?\})\)</function>",
    re.DOTALL,
)

def _is_malformed(text: str) -> bool:
    return any(p in text for p in _MALFORMED_PATTERNS)

def _extract_malformed_tool_call(text: str) -> tuple[str, dict] | None:
    match = _MALFORMED_TOOL_RE.search(text)
    if not match:
        return None

    tool_name = match.group(1)
    args_text = match.group(2)
    try:
        tool_args = json.loads(args_text)
    except json.JSONDecodeError:
        try:
            tool_args = json.loads(args_text.encode("utf-8").decode("unicode_escape"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logging.warning(f"[Agent] Could not parse malformed tool args: {args_text}")
            return None

    return tool_name, tool_args

def _format_direct_tool_result(tool_name: str, result: dict) -> str:
    if not result.get("success", False):
        return f"Tool failed with error: {result.get('error', 'Unknown error')}"

    if tool_name == "find_file":
        matches = result.get("matches", [])
        if not matches:
            return "No matching files found."
        heading = f"Found {len(matches)} matching file{'s' if len(matches) != 1 else ''}:"
        return heading + "\n" + "\n".join(matches)

    return json.dumps(result, indent=2)

def _try_run_malformed_tool(text: str) -> dict | None:
    parsed = _extract_malformed_tool_call(text)
    if not parsed:
        return None

    tool_name, tool_args = parsed
    tool_fn = TOOL_REGISTRY.get(tool_name)
    if not tool_fn:
        return None

    logging.warning(f"[Agent] Recovering malformed tool call: {tool_name} args={tool_args}")
    try:
        result = tool_fn(**tool_args)
    except Exception as e:
        logging.error(f"[Agent][Recovered Tool: {tool_name}] Failed: {e}", exc_info=True)
        result = {"success": False, "error": str(e)}

    return {
        "response": _format_direct_tool_result(tool_name, result),
        "tools_used": [tool_name],
        "success": bool(result.get("success", False)),
    }

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
    format_retries = 0

    for iteration in range(MAX_TOOL_ITERATIONS):

        # LLM call
        try:
            response = call_llm(
                [{"role": "system", "content": _build_system_prompt()}] + history,
                tools=TOOL_SCHEMAS
            )
        except Exception as e:
            err = str(e)
            is_format_error = (
                "tool_use_failed"             in err or
                "Failed to call a function"   in err or
                "tool call validation failed" in err
            )
            recovered = _try_run_malformed_tool(err) if is_format_error else None
            if recovered:
                history.append({"role": "assistant", "content": recovered["response"]})
                save_history(history)
                return recovered

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
                recovered = _try_run_malformed_tool(final_text)
                if recovered:
                    history.append({"role": "assistant", "content": recovered["response"]})
                    save_history(history)
                    return recovered

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

            # Confirmation required — not a failure, relay the message and stop
            if result.get("requires_confirmation"):
                logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Awaiting user confirmation.")
                confirmation_msg = result.get("message", "This action requires your confirmation to proceed.")
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": confirmation_msg,
                })
                # Let llm relay the confirmation request to the user, then stop
                continue

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
