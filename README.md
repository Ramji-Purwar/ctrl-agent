# ctrl-agent

A minimal Windows background application for background Gmail monitoring, local file operations, and GitHub tools.

## What it does

- **Intelligent Gmail Monitoring:** Runs in the background to monitor your inbox, automatically identifying and sorting important emails into actionable tasks while filtering out non-essential mail.
- **Secure Local File Operations:** Provides streamlined tools to find, read, and open whitelisted files and folders, keeping system management scoped to your configured base directory.
- **Integrated GitHub Tools:** View repository status, review commits, push/pull changes, manage branches, and interact with remote repositories easily.

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

## Architecture

- **Backend:** Python + Flask (API and static serving), Pywebview (UI window), APScheduler (background tasks), Pystray (system tray).
- **Frontend:** Vanilla HTML/JS/CSS (`chat_ui/`), Server-Sent Events (SSE) for live task updates.
- **Single-instance:** Launching a second instance will detect the running process and activate the existing window.

## Troubleshooting

- **"No GROQ API key found"** — check your `.env` file exists in the project root and the variable names match exactly.
- **File or folder operation fails silently** — the target path is likely outside `BASE_DIR`. Check the value set in `.env` and confirm the path is inside it.
- **Access is denied during build** — `ctrl-agent.exe` is currently running in the background. Right-click the system tray icon, select "Quit", and run `python build.py` again.
