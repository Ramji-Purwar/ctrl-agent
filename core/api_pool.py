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

COOLDOWN_FILE = Path("data/api_cooldowns.json")
COOLDOWN_SECS = 60

# Cache clients so we don't reinstantiate on every call
_clients: dict[str, genai.Client] = {}

# Round-robin cycle so all keys share load equally
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
    rate_limit_keywords = ["rate", "quota", "exhaust", "resource_exhausted", "429"]
    return any(kw in err for kw in rate_limit_keywords)


def call_gemini(messages: list, tools: list | None = None):
    cooldowns = _load_cooldowns()
    last_error = None
    start = next(_key_cycle)

    for i in range(len(GEMINI_KEYS)):
        key = GEMINI_KEYS[(start + i) % len(GEMINI_KEYS)]
        key_label = f"Key #{(start + i) % len(GEMINI_KEYS) + 1}"

        if not _is_available(key, cooldowns):
            remaining = int(cooldowns[key] - time.time())
            logging.warning(f"[APIPool] {key_label} is cooling down, {remaining}s left — skipping")
            continue

        try:
            logging.debug(f"[APIPool] Trying {key_label}...")
            client = _get_client(key)

            config = types.GenerateContentConfig(
                temperature=MODEL_CONFIG.get("temperature"),
                max_output_tokens=MODEL_CONFIG.get("max_tokens"),
                tools=tools or [],
            )

            response = client.models.generate_content(
                model=MODEL_CONFIG["name"],
                contents=messages,
                config=config,
            )

            logging.debug(f"[APIPool] {key_label} succeeded.")
            return response

        except Exception as exc:
            err = str(exc).lower()
            last_error = exc
            logging.error(f"[APIPool] {key_label} error: {exc}")

            if _is_rate_limit_error(err):
                cooldowns[key] = time.time() + COOLDOWN_SECS
                _save_cooldowns(cooldowns)
                logging.warning(f"[APIPool] {key_label} rate limited; cooldown {COOLDOWN_SECS}s")
                continue

            # Non-rate-limit error — raise immediately, don't try other keys
            raise

    min_wait = min(
        [int(v - time.time()) for v in cooldowns.values() if v > time.time()],
        default=COOLDOWN_SECS,
    )
    raise Exception(
        f"All API keys are rate limited. Retry in ~{min_wait}s. Last error: {last_error}"
    )