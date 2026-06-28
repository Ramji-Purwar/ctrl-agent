import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def _runtime_root_candidates() -> list[Path]:
    candidates: list[Path] = []

    def add(path: Path):
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser().absolute()
        if resolved not in candidates:
            candidates.append(resolved)

    add(Path.cwd())

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        add(exe_dir)
        if exe_dir.name.lower() == "dist":
            add(exe_dir.parent)

    add(Path(__file__).resolve().parent.parent)
    return candidates


def _has_runtime_files(root: Path) -> bool:
    return (
        (root / ".env").exists()
        or (root / "data" / "gmail_credentials.json").exists()
        or (root / "data" / "gmail_token.json").exists()
    )


def _resolve_runtime_root() -> Path:
    for root in _runtime_root_candidates():
        if _has_runtime_files(root):
            return root
    return _runtime_root_candidates()[0]


APP_ROOT = _resolve_runtime_root()
DATA_DIR = APP_ROOT / "data"

_env_file = APP_ROOT / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
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
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

MODEL_CONFIG = {
    "name": MODEL_FALLBACKS[0],
    "temperature": 0.6,
    "max_tokens": 2048,
}

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1", "").strip(),
    os.getenv("GROQ_API_KEY_2", "").strip(),
    os.getenv("GROQ_API_KEY_3", "").strip(),
    os.getenv("GROQ_API_KEY_4", "").strip(),
    os.getenv("GROQ_API_KEY_5", "").strip(),
]

GROQ_KEYS = [key for key in GROQ_KEYS if key]

if not GROQ_KEYS:
    raise ValueError(
        "No GROQ API key found. Set GROQ_API_KEY_1..GROQ_API_KEY_5 in .env"
    )

for key in GROQ_KEYS:
    if len(key) < 20:
        raise ValueError("One or more GROQ API keys look invalid (too short).")

GIT_USERNAME = os.getenv("GIT_USERNAME", "").strip()
GIT_TOKEN    = os.getenv("GIT_TOKEN", "").strip()

FLASK_PORT = os.getenv("FLASK_PORT")
FLASK_HOST = os.getenv("FLASK_HOST")

GMAIL_CREDENTIALS_FILE = str(DATA_DIR / "gmail_credentials.json")
GMAIL_TOKEN_FILE       = str(DATA_DIR / "gmail_token.json")
GMAIL_CACHE_FILE       = str(DATA_DIR / "email_cache.json")
GMAIL_RULES_FILE       = str(DATA_DIR / "rules.json")
CONVERSATION_FILE      = str(DATA_DIR / "conversation.json")

# Scheduler
SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL", "20"))
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"


def runtime_path(relative_path: str) -> str:
    return str(APP_ROOT / relative_path)


def resource_path(relative_path: str) -> str:
    """Get static bundled resources in dev and PyInstaller builds."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return str(Path(__file__).resolve().parent.parent / relative_path)