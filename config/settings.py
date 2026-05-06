import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR")

MODEL_FALLBACKS = [
    'llama-3.3-70b-versatile',   # best quality on Groq
    'llama-4-scout-17b-16e-instruct',  # fallback
]

MODEL_CONFIG = {
    'name': MODEL_FALLBACKS[0],
    'temperature': 0.6,
    'max_tokens': 2048,
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_KEY:
    raise ValueError("No GROQ API key found. Set GROQ_API_KEY in .env")
if len(GROQ_KEY) < 20:
    raise ValueError("GROQ API key looks invalid (too short).")