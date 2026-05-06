import logging
from openai import OpenAI
from config.settings import OPENROUTER_KEY, MODEL_CONFIG

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_KEY,
        )
    return _client


def call_llm(messages: list, tools=None) -> object:
    """
    messages: list of dicts {"role": "...", "content": "..."}
    Returns: OpenAI ChatCompletion response object
    """
    client = _get_client()

    kwargs = {
        "model": MODEL_CONFIG["name"],
        "messages": messages,
        "temperature": MODEL_CONFIG["temperature"],
        "max_tokens": MODEL_CONFIG["max_tokens"],
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        logging.debug(f"[APIPool] Calling {MODEL_CONFIG['name']}...")
        response = client.chat.completions.create(**kwargs)
        logging.debug(f"[APIPool] Success.")
        return response
    except Exception as exc:
        logging.error(f"[APIPool] Error: {exc}")
        raise