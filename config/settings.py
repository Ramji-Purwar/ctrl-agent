import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR") 

PROVIDER = "openrouter"

MODEL_CONFIG = {
    'name': 'google/gemma-4-31b-it:free',
    'temperature': 0.6,
    'max_tokens': 2048,
}

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

GEMINI_KEYS = [
    k.strip() for k in os.getenv("GOOGLE_API_KEYS", "").split(",") if k.strip()
]

if not GEMINI_KEYS:
    raise ValueError("No GEMINI API keys found. Check your .env file.")

for i, key in enumerate(GEMINI_KEYS):
    if len(key) < 20:
        raise ValueError(f"GEMINI key {i+1} looks invalid (too short).")

if PROVIDER == "gemini":
    if not GEMINI_KEYS:
        raise ValueError("No Gemini API keys found.")
elif PROVIDER == "openrouter":
    if not OPENROUTER_KEY:
        raise ValueError("No OpenRouter API key found. Set OPENROUTER_API_KEY in .env")