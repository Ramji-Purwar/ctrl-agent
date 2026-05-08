import logging
import time
from openai import OpenAI
from config.settings import GROQ_KEYS, MODEL_CONFIG, MODEL_FALLBACKS

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

_clients = {}
_key_index = 0

RETRY_DELAY = 10
RETRIES_PER_MODEL = 3

def _get_next_key() -> str:
    global _key_index
    key = GROQ_KEYS[_key_index % len(GROQ_KEYS)]
    _key_index += 1
    return key


def _get_client(api_key: str) -> OpenAI:
    client = _clients.get(api_key)
    if client is None:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        )
        _clients[api_key] = client
    return client


def call_llm(messages: list, tools=None) -> object:
    for model in MODEL_FALLBACKS:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": MODEL_CONFIG["temperature"],
            "max_tokens": MODEL_CONFIG["max_tokens"],
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        for attempt in range(1, RETRIES_PER_MODEL + 1):
            try:
                logging.debug(f"[APIPool] [{model}] Attempt {attempt}/{RETRIES_PER_MODEL}...")
                api_key = _get_next_key()
                client = _get_client(api_key)
                response = client.chat.completions.create(**kwargs)
                logging.debug(f"[APIPool] [{model}] Success.")
                return response
            except Exception as exc:
                err = str(exc)
                if "429" in err:
                    if attempt < RETRIES_PER_MODEL:
                        logging.warning(f"[APIPool] [{model}] Rate limited. Waiting {RETRY_DELAY}s...")
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        logging.warning(f"[APIPool] [{model}] All retries exhausted, trying next model...")
                        break
                logging.error(f"[APIPool] [{model}] Error: {exc}")
                raise

    raise Exception("All models rate limited. Try again later.")