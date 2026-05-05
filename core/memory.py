# memory.py
import json
import logging
from pathlib import Path
from google.genai import types

HISTORY_FILE = Path("data/conversation.json")
MAX_TURNS = 20

def _serialize(history: list) -> list:
    result = []
    for item in history:
        if isinstance(item, types.Content):
            parts = []
            for p in item.parts:
                if hasattr(p, "text") and p.text:
                    parts.append({"text": p.text})
                elif hasattr(p, "function_call") and p.function_call:
                    parts.append({"function_call": {"name": p.function_call.name, "args": dict(p.function_call.args)}})
                elif hasattr(p, "function_response") and p.function_response:
                    parts.append({"function_response": {"name": p.function_response.name, "response": p.function_response.response}})
            result.append({"role": item.role, "parts": parts})
        else:
            result.append(item)
    return result

def _deserialize(history: list) -> list:
    result = []
    for item in history:
        parts = []
        for p in item.get("parts", []):
            if "text" in p:
                parts.append(types.Part(text=p["text"]))
            elif "function_call" in p:
                parts.append(types.Part(function_call=types.FunctionCall(name=p["function_call"]["name"], args=p["function_call"]["args"])))
            elif "function_response" in p:
                parts.append(types.Part(function_response=types.FunctionResponse(name=p["function_response"]["name"], response=p["function_response"]["response"])))
        result.append(types.Content(role=item["role"], parts=parts))
    return result

def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return _deserialize(raw)
    except Exception as e:
        logging.warning(f"[Memory] Could not load history: {e}")
    return []

def save_history(history: list) -> None:
    try:
        trimmed = history[-(MAX_TURNS * 2):]
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(_serialize(trimmed), indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"[Memory] Could not save history: {e}")

def clear_history() -> None:
    try:
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        logging.info("[Memory] History cleared.")
    except Exception as e:
        logging.error(f"[Memory] Could not clear history: {e}")