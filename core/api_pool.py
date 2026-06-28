import time
import logging
import re
from openai import OpenAI
from config.settings import GROQ_KEYS, MODEL_CONFIG, MODEL_FALLBACKS

_clients    = {}
_cooldowns  = {}
_key_index  = 0

COOLDOWN_SECS     = 60
RETRY_DELAY       = 10


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


def _cooldown_key(key: str, err_msg: str = ""):
    wait_secs = COOLDOWN_SECS
    match = re.search(r'try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d\.]+)s)?', err_msg.lower())
    if match:
        h = float(match.group(1) or 0)
        m = float(match.group(2) or 0)
        s = float(match.group(3) or 0)
        parsed = h * 3600 + m * 60 + s
        if parsed > 0:
            wait_secs = parsed

    _cooldowns[key] = time.time() + wait_secs
    logging.warning(f"[APIPool] Key ...{key[-4:]} put on cooldown for {wait_secs:.0f}s")


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

        tried_keys: set = set()
        while True:
            keys = _available_keys()
            untried = [k for k in keys if k not in tried_keys]

            if not untried:
                # All available keys tried for this model — move on
                if len(tried_keys) < len(GROQ_KEYS):
                    # Some keys still on cooldown; wait for the shortest one
                    wait = min(
                        max(0, _cooldowns.get(k, 0) - time.time())
                        for k in GROQ_KEYS if k in _cooldowns
                    )
                    wait = min(wait or RETRY_DELAY, RETRY_DELAY)
                    logging.warning(f"[APIPool] All keys on cooldown — waiting {wait:.0f}s...")
                    time.sleep(wait)
                    untried = [k for k in _available_keys() if k not in tried_keys]
                    if not untried:
                        break  # still none — try next model
                else:
                    break  # every key was tried

            key = untried[_key_index % len(untried)]
            _key_index += 1
            tried_keys.add(key)

            try:
                logging.debug(f"[APIPool] [{model}] Trying key ...{key[-4:]}")
                response = _get_client(key).chat.completions.create(**kwargs)
                logging.info(f"[APIPool] [{model}] Success with key ...{key[-4:]}")
                return response

            except Exception as exc:
                err = str(exc)
                if "429" in err or "rate_limit" in err.lower():
                    _cooldown_key(key, err)
                    logging.warning(
                        f"[APIPool] [{model}] Rate limited on key ...{key[-4:]}, "
                        f"trying next available key..."
                    )
                    continue
                elif "413" in err or "too large" in err.lower():
                    # Payload too large — not a key issue, raise immediately
                    logging.error(f"[APIPool] [{model}] Payload too large (conversation too long)")
                    raise
                else:
                    logging.error(f"[APIPool] [{model}] Error: {exc}")
                    raise

        logging.warning(f"[APIPool] [{model}] All keys exhausted, trying next model...")

    raise Exception("All models and keys exhausted. Try again later.")