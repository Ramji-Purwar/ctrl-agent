from core.api_pool import call_gemini
from tools.registry import TOOL_REGISTRY, GEMINI_TOOL_SCHEMAS
from core.memory import load_history, save_history
from google.genai import types
import logging

MAX_TOOL_ITERATIONS = 15

def run_agent(user_message: str) -> dict:

    history = load_history()
    history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    tools_used = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = call_gemini(history, tools=GEMINI_TOOL_SCHEMAS)
        except Exception as e:
            logging.error(f"[Agent][Iter {iteration}] Gemini call failed: {e}")
            return {
                "response": f"API error: {e}. Try again in a moment.",
                "tools_used": tools_used,
                "success": False
            }

        part = response.candidates[0].content.parts[0]

        # Final answer — no more tool calls
        if not hasattr(part, "function_call") or part.function_call is None:
            final_text = part.text
            history.append(types.Content(role="model", parts=[types.Part(text=final_text)]))
            save_history(history)
            return {
                "response": final_text,
                "tools_used": tools_used,
                "success": True
            }

        # Extract tool call
        fn_call = part.function_call
        tool_name = fn_call.name
        tool_args = dict(fn_call.args)

        logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Args: {tool_args}")
        history.append(types.Content(role="model", parts=[part]))
        tools_used.append(tool_name)

        # Execute tool
        tool_fn = TOOL_REGISTRY.get(tool_name)
        if tool_fn:
            result = tool_fn(**tool_args)
        else:
            result = {"success": False, "error": f"Tool not found: {tool_name}"}

        # Explicitly inform Gemini when a tool fails
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error")
            logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Failed: {error_msg}")
            history.append(types.Content(
                role="user",
                parts=[types.Part(text=f"Tool '{tool_name}' failed with error: {error_msg}. "
                                       f"Tell the user what went wrong and what they can do.")]
            ))
        else:
            logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Success")
            history.append(types.Content(
                role="user",
                parts=[types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response=result
                    )
                )]
            ))

    save_history(history)
    return {
        "response": "Reached max iterations. Try breaking your request into smaller steps.",
        "tools_used": tools_used,
        "success": False
    }