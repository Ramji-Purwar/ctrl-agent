# ctrl-agent

A minimal Windows-first CLI agent that uses Groq-hosted LLMs with a safe, deterministic tool layer for local file system operations.

## What it does

- Chat via a simple CLI loop.
- Uses Groq LLMs with automatic model fallback and per-key cooldowns.
- Provides safe, whitelisted tools for file and folder operations scoped to a configured base directory.
- Persists short conversation history to disk.

## Requirements

- Windows
- Python 3.10+
- A Groq API key (one or more)

## Install

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Create a `.env` file in the project root:

```env
# Required — at least one key
GROQ_API_KEY_1=your_key_here

# Optional extra keys for fallback rotation
GROQ_API_KEY_2=your_key_here
GROQ_API_KEY_3=your_key_here
GROQ_API_KEY_4=your_key_here

# Optional — root directory for all file/folder tools
# Defaults to your user home directory if not set
BASE_DIR=C:\Users\you\projects
```

`BASE_DIR` is the only directory the agent can read, write, or open. Set it to wherever your actual work lives — the tighter the better.

## Run

```bash
python cli.py
```

Commands:

- `quit` — exit the CLI
- `clear` — wipe stored conversation history

## Project layout

```
cli.py
config/
    settings.py
core/
    agent_loop.py
    api_pool.py
    memory.py
    task_queue.py
docs/
    plan.md
tests/
    test_agent.py
    test_agent_2.py
tools/
    cmd_tools.py
    registry.py
```

## Model

Uses `llama3-groq-70b-8192-tool-use-preview` via Groq — a tool-use fine-tune of Llama 3 70b. Configured in `core/api_pool.py`.

## Troubleshooting

**"No GROQ API key found"** — check your `.env` file exists in the project root and the variable names match exactly.

**File or folder operation fails silently** — the target path is likely outside `BASE_DIR`. Check the value set in `.env` and confirm the path is inside it.

**All API keys on cooldown** — you've hit rate limits on all keys. The agent will tell you how long to wait. Adding more keys in `.env` reduces how often this happens.
