import json
import logging
from core.api_pool import call_llm
from tools.registry import TOOL_REGISTRY, OPENAI_TOOL_SCHEMAS
from core.memory import load_history, save_history

MAX_TOOL_ITERATIONS = 15

SYSTEM_PROMPT = (
    "You are a helpful personal assistant and local file system agent running on Windows. "
    "You can answer general questions and also use tools to manage files and folders. "
    "When a tool returns file content, always display the full content verbatim. "
    "Never summarize or truncate file contents unless the user explicitly asks."
)

def run_agent(user_message: str) -> dict:
    history = load_history()
    history.append({"role": "user", "content": user_message})
    tools_used = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            messages_with_system = [{"role": "system", "content": SYSTEM_PROMPT}] + history
            response = call_llm(messages_with_system, tools=OPENAI_TOOL_SCHEMAS)
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

    save_history(history)
    return {
        "response": "Reached max iterations. Try breaking your request into smaller steps.",
        "tools_used": tools_used,
        "success": False
    }