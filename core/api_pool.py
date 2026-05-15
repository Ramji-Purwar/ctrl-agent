import time
import logging
from openai import OpenAI
from config.settings import GROQ_KEYS, MODEL_CONFIG, MODEL_FALLBACKS

_clients    = {}
_cooldowns  = {}
_key_index  = 0

COOLDOWN_SECS     = 60
RETRY_DELAY       = 10
RETRIES_PER_MODEL = 3


def _get_client(api_key: str) -> OpenAI:
    if api_key not in _clients:
        _clients[api_key] = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        )
    return _clients[api_key]


def _available_keys() -> list:
    now = time.time()
    return [k for k in GROQ_KEYS if _cooldowns.get(k, 0) < now]


def _cooldown_key(key: str):
    _cooldowns[key] = time.time() + COOLDOWN_SECS
    logging.warning(f"[APIPool] Key ...{key[-4:]} put on cooldown for {COOLDOWN_SECS}s")


def call_llm(messages: list, tools=None) -> object:
    global _key_index

    for model in MODEL_FALLBACKS:
        kwargs = {
            "model":       model,
            "messages":    messages,
            "temperature": MODEL_CONFIG["temperature"],
            "max_tokens":  MODEL_CONFIG["max_tokens"],
        }
        if tools:
            kwargs["tools"]       = tools
            kwargs["tool_choice"] = "auto"

        for attempt in range(1, RETRIES_PER_MODEL + 1):
            keys = _available_keys()
            if not keys:
                logging.warning(f"[APIPool] All keys on cooldown — waiting {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                keys = _available_keys()
                if not keys:
                    break  # try next model

            key = keys[_key_index % len(keys)]   # round-robin pick
            _key_index += 1                       # advance for next call

            try:
                logging.debug(f"[APIPool] [{model}] Attempt {attempt} with key ...{key[-4:]}")
                response = _get_client(key).chat.completions.create(**kwargs)
                logging.debug(f"[APIPool] [{model}] Success.")
                return response

            except Exception as exc:
                err = str(exc)
                if "429" in err or "rate_limit" in err.lower():
                    _cooldown_key(key)
                    logging.warning(
                        f"[APIPool] [{model}] Rate limited on key ...{key[-4:]}, "
                        f"trying next available key..."
                    )
                    continue
                elif "413" in err or "too large" in err.lower():
                    logging.error(f"[APIPool] [{model}] Request too large: {exc}")
                    raise
                else:
                    logging.error(f"[APIPool] [{model}] Error: {exc}")
                    raise

        logging.warning(f"[APIPool] [{model}] All attempts failed, trying next model...")

    raise Exception("All models and keys exhausted. Try again later.")