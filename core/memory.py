import json
import logging
from pathlib import Path

HISTORY_FILE = Path("data/conversation.json")
MAX_TURNS = 20

def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"[Memory] Could not load history: {e}")
    return []

def save_history(history: list) -> None:
    try:
        # Trim to last MAX_TURNS pairs before saving
        trimmed = history[-(MAX_TURNS * 2):]
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"[Memory] Could not save history: {e}")

def clear_history() -> None:
    try:
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        logging.info("[Memory] History cleared.")
    except Exception as e:
        logging.error(f"[Memory] Could not clear history: {e}")