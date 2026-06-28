# ctrl-agent

A powerful Windows background application that automates Gmail triage, local file operations, and GitHub workflows—all accessible via a natural-language chat widget. **ctrl-agent** also acts as a native **Model Context Protocol (MCP) Server**, allowing external LLM clients like Claude Desktop to securely interact with your local environment.

## What it does

- **Intelligent Gmail Monitoring:** Runs in the background to monitor your inbox, using a two-pass classification engine (rules + Groq API) to sort emails into actionable tasks, filtering out non-essential mail.
- **Secure Local File Operations:** Provides streamlined tools to find, read, and manage whitelisted files and folders, keeping system operations securely scoped to your configured base directory.
- **Integrated GitHub Tools:** View repository status, review commits, manage branches, and push/pull changes directly from the agent's interface.
- **Native MCP Server:** Exposes your local tools to external AI clients. Watch as Claude Desktop autonomously runs Git commands or searches your files, with all actions streamed live to your `ctrl-agent` widget via Server-Sent Events (SSE).

## Requirements

- Windows
- Python 3.10+
- **Groq API Key** (Set in `.env`)
- **GitHub Personal Access Token**:
  - Follow the [GitHub Personal Access Token Guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) to generate a token. It requires the `repo` scope.
- **Gmail OAuth Credentials**:
  - Follow the [Google Workspace Auth Guide](https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application) to create Desktop application credentials.
  - Download the credentials file, rename it to `gmail_credentials.json`, and place it in the `data/` folder inside this project folder: [data/gmail_credentials.json].

## Install

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Create a `.env` file in the project root:

```env
BASE_DIR=C:\Users\...

GROQ_API_KEY_1=your_groq_key_1
GROQ_API_KEY_2=your_groq_key_2
GROQ_API_KEY_3=your_groq_key_3
GROQ_API_KEY_4=your_groq_key_4

GIT_USERNAME=Ramji-Purwar
GIT_TOKEN=your_github_token

FLASK_PORT=9999
FLASK_HOST=127.0.0.1

SCHEDULER_INTERVAL=20
SCHEDULER_ENABLED=true
```

## Run and Build

### Development Mode

Run the app in development mode:

```bash
python run_chat.py
```

### Build Executable

Compile the project into a standalone Windows executable (`dist/ctrl-agent.exe`):

```bash
python build.py
```

### Windows Integration

Register the compiled executable with Windows Search and set it to launch on boot:

```bash
python startup.py register    # Adds to Start Menu
python startup.py enable      # Sets to auto-start on Windows boot
python startup.py status      # Check current shortcut state
```

## Usage & Keyboard Shortcuts

- **`Ctrl+Alt+C`** — Show/restore the chat window globally.
- **`Ctrl+L`** (in chat) — Clear chat history.
- **`↑` / `↓`** (in chat) — Navigate command history.
- **Close (X) Button** — Hides the window to the system tray (the background processes keep running).
- **Task Done Button ($\checkmark$)** — Mark a task as completed (removes it from the active sidebar task listing and updates its category in the cache to `"info"`).
- **System Tray Icon** — Right-click to completely `Quit` the application or manually trigger an email check.

## Model Context Protocol (MCP) Integration

This project includes a native MCP server (`mcp_server.py`) that allows external LLM clients (such as **Claude Desktop**) to directly invoke all `ctrl-agent` tools.

When Claude calls a tool via the MCP server:
1. The tool executes locally (e.g., performing a Git command, searching files, or calling Gmail).
2. The MCP server notifies the running `ctrl-agent` Flask application via `POST /mcp-event`.
3. The activity is instantly displayed in your `ctrl-agent` chat/task window, so you can track Claude's actions in real-time.

### Claude Desktop Configuration

Add the following to your `claude_desktop_config.json` (located at `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ctrl-agent": {
      "command": "C:\\Users\\r4849\\Desktop\\ctrl-agent\\venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\r4849\\Desktop\\ctrl-agent\\mcp_server.py"
      ]
    }
  }
}
```

*Note: Make sure to adjust the paths if your project location or Python environment is different.*

## Architecture

- **Backend:** Python + Flask (API and static serving), Pywebview (UI window), APScheduler (background tasks), Pystray (system tray).
- **Frontend:** Vanilla HTML/JS/CSS (`chat_ui/`), Server-Sent Events (SSE) for live task updates.
- **Single-instance:** Launching a second instance will detect the running process and activate the existing window.
- **MCP Server:** Python + stdio transport for direct LLM integration.

## Troubleshooting

- **"No GROQ API key found"** — check your `.env` file exists in the project root and the variable names match exactly.
- **File or folder operation fails silently** — the target path is likely outside `BASE_DIR`. Check the value set in `.env` and confirm the path is inside it.
- **Access is denied during build** — `ctrl-agent.exe` is currently running in the background. Right-click the system tray icon, select "Quit", and run `python build.py` again.
- **MCP Server connection errors in Claude Desktop** — Check the logs at `data/mcp_server.log` for any startup or tool execution errors. Make sure the virtual environment has all the packages from `requirements.txt` installed.

