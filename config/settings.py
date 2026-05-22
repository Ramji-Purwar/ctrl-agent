import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_BASE_DIR = os.getenv("BASE_DIR") or os.path.expanduser("~")
_BASE_DIR = str(Path(os.path.expandvars(os.path.expanduser(_DEFAULT_BASE_DIR))).resolve())


def get_base_dir() -> str:
    return _BASE_DIR


def get_default_base_dir() -> str:
    return str(Path(os.path.expandvars(os.path.expanduser(_DEFAULT_BASE_DIR))).resolve())


def set_base_dir(path: str) -> str:
    global _BASE_DIR

    expanded = Path(os.path.expandvars(os.path.expanduser(path)))
    if not expanded.is_absolute():
        expanded = Path(_BASE_DIR) / expanded

    resolved = expanded.resolve()
    default_base = Path(get_default_base_dir()).resolve()

    if not resolved.is_relative_to(default_base):
        raise ValueError(f"Cannot cd outside default base directory: {default_base}")
    if not resolved.exists():
        raise ValueError(f"Directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {resolved}")

    _BASE_DIR = str(resolved)
    return _BASE_DIR


def reset_base_dir() -> str:
    return set_base_dir(get_default_base_dir())


BASE_DIR = get_base_dir()

MODEL_FALLBACKS = [
    'llama-3.3-70b-versatile',
    'llama-3.1-8b-instant',
]

MODEL_CONFIG = {
    'name': MODEL_FALLBACKS[0],
    'temperature': 0.6,
    'max_tokens': 2048,
}

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1", "").strip(),
    os.getenv("GROQ_API_KEY_2", "").strip(),
    os.getenv("GROQ_API_KEY_3", "").strip(),
    os.getenv("GROQ_API_KEY_4", "").strip(),
]
GROQ_KEYS = [key for key in GROQ_KEYS if key]

if not GROQ_KEYS:
    raise ValueError(
        "No GROQ API key found. Set GROQ_API_KEY_1..GROQ_API_KEY_4 in .env"
    )

for key in GROQ_KEYS:
    if len(key) < 20:
        raise ValueError("One or more GROQ API keys look invalid (too short).")

GIT_USERNAME = os.getenv("GIT_USERNAME", "").strip()
GIT_TOKEN    = os.getenv("GIT_TOKEN", "").strip()

FLASK_PORT = os.getenv("FLASK_PORT")
FLASK_HOST = os.getenv("FLASK_HOST")

GMAIL_CREDENTIALS_FILE = os.path.join("data", "gmail_credentials.json")
GMAIL_TOKEN_FILE       = os.path.join("data", "gmail_token.json")
GMAIL_CACHE_FILE       = os.path.join("data", "email_cache.json")
GMAIL_RULES_FILE       = os.path.join("data", "rules.json")
