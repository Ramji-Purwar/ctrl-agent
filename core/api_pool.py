import itertools
import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from config.settings import GEMINI_KEYS, MODEL_CONFIG

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

COOLDOWN_FILE = Path("data/api_cooldowns.json")
COOLDOWN_SECS = 60

_clients: dict[str, genai.Client] = {}
_key_cycle = itertools.cycle(range(len(GEMINI_KEYS)))


def _get_client(key: str) -> genai.Client:
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


def _load_cooldowns() -> dict:
    try:
        if COOLDOWN_FILE.exists():
            return json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning(f"[APIPool] Could not load cooldowns: {exc}")
    return {}


def _save_cooldowns(cooldowns: dict) -> None:
    try:
        COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.error(f"[APIPool] Could not save cooldowns: {exc}")


def _is_available(key: str, cooldowns: dict) -> bool:
    if key not in cooldowns:
        return True
    return time.time() > cooldowns[key]


def _is_rate_limit_error(err: str) -> bool:
    rate_limit_keywords = ["quota", "resource_exhausted", "429", "503", "unavailable"]
    return any(kw in err for kw in rate_limit_keywords) and "validation" not in err


def call_gemini(messages: list, tools=None, key_index: int | None = None):
    """
    Returns: (response, key_index_used)
    Pass key_index to lock to a specific key for multi-turn tool calls.
    """
    cooldowns = _load_cooldowns()
    last_error = None
    start = key_index if key_index is not None else next(_key_cycle)

    for i in range(len(GEMINI_KEYS)):
        # If locked to a specific key, only try that one
        if key_index is not None:
            idx = key_index
        else:
            idx = (start + i) % len(GEMINI_KEYS)

        key = GEMINI_KEYS[idx]
        key_label = f"Key #{idx + 1}"

        if not _is_available(key, cooldowns):
            remaining = int(cooldowns[key] - time.time())
            logging.warning(f"[APIPool] {key_label} is cooling down, {remaining}s left — skipping")
            if key_index is not None:
                # Locked key is on cooldown — try other keys
                key_index = None
                start = next(_key_cycle)
                continue
            continue

        try:
            logging.debug(f"[APIPool] Trying {key_label}...")
            client = _get_client(key)

            config = types.GenerateContentConfig(
                temperature=MODEL_CONFIG.get("temperature"),
                max_output_tokens=MODEL_CONFIG.get("max_tokens"),
                tools=[tools] if tools else [],
            )

            response = client.models.generate_content(
                model=MODEL_CONFIG["name"],
                contents=messages,
                config=config,
            )

            logging.debug(f"[APIPool] {key_label} succeeded.")
            return response, idx

        except Exception as exc:
            err = str(exc).lower()
            last_error = exc
            logging.error(f"[APIPool] {key_label} error: {exc}")

            if _is_rate_limit_error(err):
                cooldowns[key] = time.time() + COOLDOWN_SECS
                _save_cooldowns(cooldowns)
                logging.warning(f"[APIPool] {key_label} rate limited; cooldown {COOLDOWN_SECS}s")
                if key_index is not None:
                    # Locked key rate limited — unlock and try others
                    key_index = None
                    start = next(_key_cycle)
                continue

            raise

    min_wait = min(
        [int(v - time.time()) for v in cooldowns.values() if v > time.time()],
        default=COOLDOWN_SECS,
    )
    raise Exception(
        f"All API keys are rate limited. Retry in ~{min_wait}s. Last error: {last_error}"
    )