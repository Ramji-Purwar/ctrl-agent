import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR") or os.path.expanduser("~")

MODEL_FALLBACKS = [
    'llama3-groq-70b-8192-tool-use-preview'
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