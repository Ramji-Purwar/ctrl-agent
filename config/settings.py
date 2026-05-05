import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR") 

MODEL_CONFIG = {
    'name': 'gemini-3.1-flash-lite-preview',
    'temperature': 0.6,
    'max_tokens': 2048,
}

GEMINI_KEYS = [
    k.strip() for k in os.getenv("GOOGLE_API_KEYS", "").split(",") if k.strip()
]

if not GEMINI_KEYS:
    raise ValueError("No GEMINI API keys found. Check your .env file.")

for i, key in enumerate(GEMINI_KEYS):
    if len(key) < 20:
        raise ValueError(f"GEMINI key {i+1} looks invalid (too short).")