# Windows AI Agent — Final Practical Design (v2.1)

> **Goal:** Build a system you actually use daily  
> **Principle:** Reliability > Intelligence > Features  
> **Rule:** If it annoys you twice, you will stop using it.

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Project Structure](#2-project-structure)
3. [Agent Loop — Failure-Aware](#3-agent-loop--failure-aware)
4. [API Pool — Failure-Based Fallback](#4-api-pool--failure-based-fallback)
5. [Task Queue — Priority + Non-Blocking](#5-task-queue--priority--non-blocking)
6. [Tools — Deterministic First](#6-tools--deterministic-first)
7. [Gmail Pipeline — Batch + JSON Output](#7-gmail-pipeline--batch--json-output)
8. [Widget — Event-Driven + Bounded Queue](#8-widget--event-driven--bounded-queue)
9. [System Safety](#9-system-safety)
10. [Logging — Structured](#10-logging--structured)
11. [Flask API](#11-flask-api)
12. [Config & Storage](#12-config--storage)
13. [Data Flow](#13-data-flow)
14. [Build Order — CLI First](#14-build-order--cli-first)
15. [Tech Stack](#15-tech-stack)
16. [What Goes to LLM vs What Stays Deterministic](#16-what-goes-to-llm-vs-what-stays-deterministic)

---

## 1. Core Philosophy

**Prefer deterministic logic over AI wherever possible.**  
The LLM is expensive, slow, and occasionally wrong. Use it only when nothing else works.

| Decision | Approach |
|----------|----------|
| Is this email from my professor? | Rules file — no LLM |
| Is this email urgent? | Keyword match — no LLM |
| What does this ambiguous email mean? | LLM |
| Run git status | subprocess — no LLM |
| Summarize my emails for me | LLM |
| Make a folder | Python os — no LLM |

**Other principles:**
- Avoid surprises. The agent should do exactly what you expect.
- Fail loudly. Silent failures are worse than visible errors.
- Minimize LLM calls. Every unnecessary call wastes quota and adds latency.
- Build CLI first. Use it for 2–3 days before adding any UI.
- If it annoys you twice, fix it immediately or remove it.

---

## 2. Project Structure

```
ai-agent/
│
├── core/
│   ├── agent_loop.py          # Failure-aware multi-step tool calling loop
│   ├── api_pool.py            # Sequential fallback + per-key cooldown
│   ├── task_queue.py          # Priority queue, non-blocking per-task sync
│   └── memory.py              # Conversation history (persist + reload)
│
├── tools/
│   ├── registry.py            # Tool registry + Gemini function schemas
│   ├── cmd_tools.py           # Whitelisted CMD ops, BASE_DIR enforced
│   ├── git_tools.py           # Git ops, confirmation + dry-run
│   └── gmail_tools.py         # Gmail wrappers returning clean dicts
│
├── gmail/
│   ├── auth.py                # OAuth2 + silent token refresh
│   ├── fetcher.py             # Fetch + local cache (skip seen IDs)
│   └── categorizer.py         # Rules-first, batch LLM, forced JSON output
│
├── scheduler/
│   └── jobs.py                # APScheduler: 15–30 min, max_instances=1
│
├── widget/
│   ├── events.py              # Bounded SSE queue (maxsize=100, drop stale)
│   ├── tray.py                # pystray system tray icon
│   ├── popup.html             # Interactive widget UI
│   └── popup.js               # SSE listener + action buttons
│
├── chat_ui/
│   ├── index.html             # Chat interface
│   └── chat.js                # Sends to /chat, shows tool trace
│
├── flask_app/
│   ├── app.py                 # Flask entry point
│   ├── routes_chat.py         # POST /chat
│   ├── routes_events.py       # GET /events (SSE stream)
│   ├── routes_action.py       # POST /action (widget buttons)
│   └── routes_setup.py        # GET/POST /setup
│
├── data/
│   ├── conversation.json      # Last 20 turns of chat history
│   ├── email_cache.json       # Cached parsed emails by ID
│   ├── notification_log.json  # Seen notification IDs (survives crash)
│   ├── api_cooldowns.json     # Per-key cooldown expiry timestamps
│   └── rules.json             # Your personal email rules
│
├── config/
│   └── settings.py            # Constants, BASE_DIR, env loading
│
├── logs/
│   └── agent.log              # Rotating structured log (5MB, 3 backups)
│
├── cli.py                     # Phase 1 entry point — no UI needed
├── setup.py                   # First-run wizard
├── run.py                     # Phase 2 — Flask + tray + scheduler
├── requirements.txt
├── .env                        # API keys (never commit)
└── .gitignore
```

---

## 3. Agent Loop — Failure-Aware

The key upgrade from v2: when a tool fails, the agent is explicitly told it failed. It cannot assume success or silently retry with wrong data.

```python
# core/agent_loop.py

from core.api_pool import call_gemini
from tools.registry import TOOL_REGISTRY, GEMINI_TOOL_SCHEMAS
from core.memory import load_history, save_history
import logging

MAX_TOOL_ITERATIONS = 10

def run_agent(user_message: str) -> dict:
    """
    Returns: {"response": str, "tools_used": list, "success": bool}
    """
    history = load_history()
    history.append({"role": "user", "parts": [user_message]})
    tools_used = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = call_gemini(history, tools=GEMINI_TOOL_SCHEMAS)
        except Exception as e:
            logging.error(f"[Agent][Iter {iteration}] Gemini call failed: {e}")
            return {
                "response": f"API error: {e}. Try again in a moment.",
                "tools_used": tools_used,
                "success": False
            }

        part = response.candidates[0].content.parts[0]

        # Final answer — no more tool calls
        if not hasattr(part, "function_call"):
            final_text = part.text
            history.append({"role": "model", "parts": [final_text]})
            save_history(history)
            return {
                "response": final_text,
                "tools_used": tools_used,
                "success": True
            }

        # Extract tool call
        fn_call = part.function_call
        tool_name = fn_call.name
        tool_args = dict(fn_call.args)

        logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Args: {tool_args}")
        history.append({"role": "model", "parts": [part]})
        tools_used.append(tool_name)

        # Execute tool
        tool_fn = TOOL_REGISTRY.get(tool_name)
        if tool_fn:
            result = tool_fn(**tool_args)
        else:
            result = {"success": False, "error": f"Tool not found: {tool_name}"}

        # KEY CHANGE: explicitly inform Gemini when a tool fails
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error")
            logging.warning(f"[Agent][Iter {iteration}][Tool: {tool_name}] Failed: {error_msg}")

            # Tell Gemini the tool failed — it cannot assume success
            history.append({
                "role": "user",
                "parts": [f"Tool '{tool_name}' failed with error: {error_msg}. "
                          f"Tell the user what went wrong and what they can do."]
            })
        else:
            logging.info(f"[Agent][Iter {iteration}][Tool: {tool_name}] Success")
            history.append({
                "role": "tool",
                "parts": [{"function_response": {
                    "name": tool_name,
                    "response": result
                }}]
            })

    save_history(history)
    return {
        "response": "Reached max iterations. Try breaking your request into smaller steps.",
        "tools_used": tools_used,
        "success": False
    }
```

**What this fixes:**
- Gemini is told explicitly when a tool fails — it stops assuming success
- Gemini will explain the failure to you instead of silently moving on
- All failures are logged with iteration number and tool name

---

## 4. API Pool — Failure-Based Fallback

No token tracking. No RPM math. Just try → fail → cooldown → next key.

```python
# core/api_pool.py

import time
import json
import logging
import google.generativeai as genai
from pathlib import Path
from config.settings import GEMINI_KEYS

COOLDOWN_FILE  = Path("data/api_cooldowns.json")
COOLDOWN_SECS  = 60   # disable key for 60s on rate limit
MODEL_NAME     = "gemini-1.5-flash"

def _load_cooldowns() -> dict:
    try:
        if COOLDOWN_FILE.exists():
            return json.loads(COOLDOWN_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_cooldowns(cd: dict):
    try:
        COOLDOWN_FILE.write_text(json.dumps(cd, indent=2))
    except Exception as e:
        logging.error(f"[APIPool] Could not save cooldowns: {e}")

def _is_available(key: str, cooldowns: dict) -> bool:
    if key not in cooldowns:
        return True
    return time.time() > cooldowns[key]

def call_gemini(messages: list, tools: list = None):
    cooldowns = _load_cooldowns()
    last_error = None

    for key in GEMINI_KEYS:
        if not _is_available(key, cooldowns):
            remaining = int(cooldowns[key] - time.time())
            logging.info(f"[APIPool] Key ...{key[-6:]} cooling down ({remaining}s left)")
            continue

        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(MODEL_NAME)
            kwargs = {"tools": tools} if tools else {}
            response = model.generate_content(messages, **kwargs)
            logging.info(f"[APIPool] Key ...{key[-6:]} succeeded")
            return response

        except Exception as e:
            err = str(e).lower()
            last_error = e

            if any(x in err for x in ["rate limit", "quota", "429", "resource exhausted"]):
                cooldowns[key] = time.time() + COOLDOWN_SECS
                _save_cooldowns(cooldowns)
                logging.warning(f"[APIPool] Key ...{key[-6:]} rate limited → cooldown {COOLDOWN_SECS}s")
                continue
            else:
                # Non-rate-limit error — don't try other keys, raise immediately
                logging.error(f"[APIPool] Key ...{key[-6:]} non-rate error: {e}")
                raise e

    # All keys exhausted
    min_wait = min(
        [int(v - time.time()) for v in cooldowns.values() if v > time.time()],
        default=COOLDOWN_SECS
    )
    raise Exception(f"All API keys rate limited. Retry in ~{min_wait} seconds.")
```

**Behavior:**
- Rate limit → cooldown that key, try the next one
- Other error (auth, network, bad request) → raise immediately, don't try more keys
- All keys exhausted → tell user exactly how long to wait
- Cooldown state persists across restarts

---

## 5. Task Queue — Priority + Non-Blocking

The v2 queue used `.join()` which blocked the entire calling thread. This fix uses per-task `Event` synchronization so each task waits only for itself.

```python
# core/task_queue.py

import queue
import threading
import logging

HIGH = 0  # user chat, widget actions
LOW  = 1  # scheduler background jobs

_queue   = queue.PriorityQueue()
_counter = 0
_lock    = threading.Lock()

def _worker():
    while True:
        priority, count, fn, args, kwargs, result_holder, done_event = _queue.get()
        try:
            result_holder["result"] = fn(*args, **kwargs)
        except Exception as e:
            result_holder["error"] = str(e)
            logging.error(f"[Queue][P{priority}] Task failed: {e}")
        finally:
            done_event.set()   # signal this specific task is done
            _queue.task_done()

# Single worker thread — one task at a time, no race conditions
threading.Thread(target=_worker, daemon=True).start()

def submit_task(fn, *args, priority: int = HIGH, timeout: int = 60, **kwargs) -> dict:
    global _counter
    result_holder = {}
    done_event    = threading.Event()

    with _lock:
        _counter += 1
        count = _counter

    _queue.put((priority, count, fn, args, kwargs, result_holder, done_event))

    completed = done_event.wait(timeout=timeout)
    if not completed:
        logging.error(f"[Queue] Task timed out after {timeout}s: {fn.__name__}")
        return {"error": f"Task timed out after {timeout}s"}

    return result_holder
```

**Usage:**
```python
# User chat — always HIGH
result = submit_task(run_agent, message, priority=HIGH, timeout=60)

# Scheduler job — always LOW, shorter timeout
result = submit_task(check_gmail_job, priority=LOW, timeout=120)
```

---

## 6. Tools — Deterministic First

### `tools/cmd_tools.py` — Path-Safe CMD

Every path is validated against `BASE_DIR` before execution. No exceptions.

```python
# tools/cmd_tools.py

import os
import subprocess
import logging
from pathlib import Path
from config.settings import BASE_DIR

def is_safe_path(path: str) -> bool:
    try:
        resolved = Path(path).resolve()
        base     = Path(BASE_DIR).resolve()
        return resolved.is_relative_to(base)
    except Exception:
        return False

def _safe_check(path: str, operation: str) -> dict | None:
    """Returns error dict if unsafe, None if safe."""
    if not is_safe_path(path):
        logging.warning(f"[CMD][{operation}] Blocked unsafe path: {path}")
        return {"success": False, "error": f"Path '{path}' is outside allowed directory '{BASE_DIR}'"}
    return None

def make_folder(path: str) -> dict:
    if err := _safe_check(path, "make_folder"): return err
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logging.info(f"[CMD][make_folder] Created: {path}")
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_file(filename: str, search_root: str) -> dict:
    if err := _safe_check(search_root, "find_file"): return err
    try:
        matches = [
            os.path.join(root, filename)
            for root, _, files in os.walk(search_root)
            if filename in files
        ]
        return {"success": True, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_folder(path: str) -> dict:
    if err := _safe_check(path, "open_folder"): return err
    try:
        subprocess.run(["explorer", path], shell=False)
        return {"success": True, "opened": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_directory(path: str) -> dict:
    if err := _safe_check(path, "list_directory"): return err
    try:
        items = os.listdir(path)
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

### `tools/git_tools.py` — Confirmation + Dry-Run

```python
# tools/git_tools.py

import subprocess
import logging
from config.settings import GITHUB_USERNAME, GITHUB_TOKEN

def _run_git(args: list, cwd: str = None) -> dict:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,        # never shell=True
            timeout=30
        )
        success = result.returncode == 0
        logging.info(f"[Git] git {' '.join(args)} → {'OK' if success else 'FAIL'}")
        if success:
            return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Git command timed out after 30s"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def git_status(repo_path: str) -> dict:
    return _run_git(["status"], cwd=repo_path)

def git_branch(repo_path: str) -> dict:
    return _run_git(["branch", "-a"], cwd=repo_path)

def git_pull(repo_path: str) -> dict:
    return _run_git(["pull"], cwd=repo_path)

def git_clone(repo_url: str, destination: str) -> dict:
    auth_url = repo_url.replace(
        "https://", f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@"
    )
    return _run_git(["clone", auth_url, destination])

def git_dry_run(repo_path: str, operation: str) -> dict:
    """Show what would happen without doing anything."""
    if operation == "push":
        status = _run_git(["status", "--short"], cwd=repo_path)
        log    = _run_git(["log", "origin/HEAD..HEAD", "--oneline"], cwd=repo_path)
        return {
            "success": True,
            "dry_run": True,
            "operation": "push",
            "would_push_commits": log.get("output") or "none",
            "changed_files": status.get("output") or "clean"
        }
    return {"success": False, "error": f"Dry run not supported for: {operation}"}

def git_push(repo_path: str, confirmed: bool = False) -> dict:
    """Requires explicit confirmation. Shows preview if not confirmed."""
    if not confirmed:
        # Return preview — do not execute
        status = _run_git(["status", "--short"], cwd=repo_path)
        log    = _run_git(["log", "origin/HEAD..HEAD", "--oneline"], cwd=repo_path)
        return {
            "success": False,
            "requires_confirmation": True,
            "preview": {
                "unpushed_commits": log.get("output") or "none",
                "changed_files": status.get("output") or "clean"
            },
            "message": "Reply 'yes, push' to confirm or 'cancel' to abort."
        }
    return _run_git(["push"], cwd=repo_path)
```

---

## 7. Gmail Pipeline — Batch + JSON Output

### `gmail/categorizer.py` — Rules First, Forced JSON from LLM

The biggest reliability fix: LLM is forced to output a JSON array. No parsing ambiguity.

```python
# gmail/categorizer.py

import json
import logging
from pathlib import Path
from core.api_pool import call_gemini

RULES_FILE = Path("data/rules.json")

def _load_rules() -> dict:
    if RULES_FILE.exists():
        return json.loads(RULES_FILE.read_text())
    return {
        "always_action_required": [],
        "always_ignore": [],
        "keywords_action": [
            "due date", "deadline", "meeting", "urgent", "exam",
            "result", "attendance", "fee", "submission", "assignment",
            "quiz", "test", "internship", "placement"
        ]
    }

def batch_categorize(emails: list) -> dict:
    rules = _load_rules()
    action_required = []
    ignore          = []
    needs_llm       = []

    # Pass 1: Rule-based (zero API cost, instant)
    for email in emails:
        sender  = email["from"].lower()
        subject = email["subject"].lower()
        body    = email["body_preview"].lower()

        if any(s in sender for s in rules["always_action_required"]):
            action_required.append(email)
        elif any(s in sender for s in rules["always_ignore"]):
            ignore.append(email)
        elif any(kw in subject or kw in body for kw in rules["keywords_action"]):
            action_required.append(email)
        else:
            needs_llm.append(email)

    # Pass 2: One batch LLM call for everything else
    if needs_llm:
        results = _batch_llm_categorize(needs_llm)
        for email, category in zip(needs_llm, results):
            if category == "action_required":
                action_required.append(email)
            else:
                ignore.append(email)

    logging.info(
        f"[Gmail][Categorizer] action={len(action_required)} "
        f"ignore={len(ignore)} llm_batch={len(needs_llm)}"
    )
    return {"action_required": action_required, "ignore": ignore}

def _batch_llm_categorize(emails: list) -> list:
    """
    One API call for all ambiguous emails.
    Forces JSON array output — no parsing guesswork.
    """
    numbered = "\n".join([
        f"{i+1}. From: {e['from']} | Subject: {e['subject']} | Preview: {e['snippet']}"
        for i, e in enumerate(emails)
    ])

    prompt = f"""You are categorizing emails for a college student.

For each email, decide: does it require action (reply, attend, submit, pay) or can it be ignored?

Respond with ONLY a valid JSON array. No explanation. No markdown. No extra text.
One string per email in order: "action_required" or "ignore"

Example for 3 emails: ["action_required", "ignore", "action_required"]

Emails:
{numbered}"""

    try:
        response = call_gemini([{"role": "user", "parts": [prompt]}])
        raw = response.text.strip()

        # Strip markdown fences if model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)

        if not isinstance(parsed, list):
            raise ValueError("Response is not a list")

        # Validate and sanitize each item
        valid = {"action_required", "ignore"}
        results = [
            item if item in valid else "ignore"
            for item in parsed
        ]

        # Pad if model returned fewer items than expected
        while len(results) < len(emails):
            results.append("ignore")

        return results[:len(emails)]

    except Exception as e:
        logging.error(f"[Gmail][Categorizer] LLM batch failed: {e} | Raw: {raw if 'raw' in dir() else 'N/A'}")
        # Safe default: mark all as ignore rather than crash
        return ["ignore"] * len(emails)
```

---

## 8. Widget — Event-Driven + Bounded Queue

### `widget/events.py` — Bounded SSE Queue

Bounded queue prevents unbounded memory growth. Stale events are dropped when full.

```python
# widget/events.py

import queue
import json
import logging

# maxsize=100 — drop stale events if widget isn't consuming them
_event_queue = queue.Queue(maxsize=100)

def push_event(event: dict):
    """Push event to widget. Drops silently if queue is full."""
    try:
        _event_queue.put_nowait(json.dumps(event))
        logging.info(f"[Widget][Event] Pushed: {event.get('type', 'unknown')}")
    except queue.Full:
        logging.warning("[Widget][Event] Queue full — dropping stale event")

def event_stream():
    """
    SSE generator. Flask route consumes this.
    Sends a keepalive comment every 15s to prevent connection timeout.
    """
    import time
    last_keepalive = time.time()

    while True:
        try:
            # Non-blocking check with short timeout for keepalive
            event = _event_queue.get(timeout=15)
            yield f"data: {event}\n\n"
        except queue.Empty:
            # Send SSE comment as keepalive (browser ignores comments)
            yield ": keepalive\n\n"
```

### `widget/popup.js` — SSE Listener + Actions

```javascript
// widget/popup.js

const source = new EventSource("http://localhost:5000/events");

source.onmessage = function(event) {
    const data = JSON.parse(event.data);
    handleEvent(data);
};

source.onerror = function() {
    // Reconnect automatically — EventSource does this by default
    document.getElementById("status").textContent = "Reconnecting...";
};

function handleEvent(data) {
    if (data.type === "new_emails") {
        renderEmails(data.emails, data.count);
        flashTrayIcon();
    } else if (data.type === "auth_error") {
        showAlert("Gmail auth expired. Open chat and type: re-authenticate gmail");
    } else if (data.type === "error") {
        showAlert(data.message);
    } else if (data.type === "clear") {
        document.getElementById("email-list").innerHTML = "No new notifications.";
    }
}

function renderEmails(emails, count) {
    const list = document.getElementById("email-list");
    list.innerHTML = `<strong>${count} action required:</strong>`;
    emails.forEach(e => {
        const card = document.createElement("div");
        card.className = "email-card";
        card.innerHTML = `
            <div class="sender">${e.from}</div>
            <div class="subject">${e.subject}</div>
        `;
        list.appendChild(card);
    });
}

// Widget action buttons → run agent at HIGH priority
async function triggerAction(action) {
    const btn = document.querySelector(`[data-action="${action}"]`);
    if (btn) btn.disabled = true;

    const res = await fetch("http://localhost:5000/action", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action})
    });

    const data = await res.json();
    document.getElementById("result").textContent = data.result;
    if (btn) btn.disabled = false;
}
```

---

## 9. System Safety

### Rules Enforced in Code

| Threat | Protection | Where |
|--------|-----------|-------|
| Path traversal | `is_safe_path()` against `BASE_DIR` | `cmd_tools.py` |
| Shell injection | `shell=False`, list args always | `cmd_tools.py`, `git_tools.py` |
| Accidental push | `confirmed=True` required + preview shown | `git_tools.py` |
| Destructive ops without review | `git_dry_run()` mode | `git_tools.py` |
| Prompt injection via email | LLM only categorizes, never executes from email content | `categorizer.py` |
| Credential exposure | `.env` file + `.gitignore` | Config |
| Unbounded memory | Bounded SSE queue (maxsize=100) | `events.py` |
| Runaway agent loop | Hard cap at 10 iterations | `agent_loop.py` |
| Hung tasks | Per-task timeout (60s chat, 120s scheduler) | `task_queue.py` |

### `.gitignore` — Non-Negotiable

```
.env
data/gmail_token.pkl
data/api_cooldowns.json
data/conversation.json
data/email_cache.json
data/notification_log.json
logs/
__pycache__/
*.pyc
```

---

## 10. Logging — Structured

Every log line follows the same format so you can `grep` for exactly what you need.

```
[Module][SubContext] Message
```

**Examples:**
```
[Agent][Iter 0][Tool: git_status] Args: {repo_path: C:/projects/app}
[Agent][Iter 0][Tool: git_status] Success
[Agent][Iter 1][Tool: git_push] Failed: authentication failed
[APIPool] Key ...abc123 succeeded
[APIPool] Key ...def456 rate limited → cooldown 60s
[Gmail][Categorizer] action=3 ignore=14 llm_batch=5
[Gmail] Token refreshed successfully
[Queue][P0] Task failed: connection timeout
[Widget][Event] Pushed: new_emails
[Scheduler] Gmail check: 2 new action-required emails
```

**Setup:**
```python
# In flask_app/app.py or run.py
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/agent.log",
    maxBytes=5_000_000,    # 5MB
    backupCount=3
)
handler.setFormatter(logging.Formatter(
    "%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

# Also print to console during development
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)
```

---

## 11. Flask API

### `flask_app/routes_chat.py`

```python
from flask import Blueprint, request, jsonify
from core.agent_loop import run_agent
from core.task_queue import submit_task, HIGH
from core.memory import clear_history

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat():
    data    = request.get_json()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"response": "Empty message"}), 400

    result = submit_task(run_agent, message, priority=HIGH, timeout=90)

    if "error" in result:
        return jsonify({"response": f"Error: {result['error']}"}), 500

    agent_result = result["result"]
    return jsonify({
        "response":   agent_result["response"],
        "tools_used": agent_result.get("tools_used", []),
        "success":    agent_result.get("success", False)
    })

@chat_bp.route("/clear_history", methods=["POST"])
def clear():
    clear_history()
    return jsonify({"success": True})
```

### `flask_app/routes_events.py`

```python
from flask import Blueprint, Response
from widget.events import event_stream

events_bp = Blueprint("events", __name__)

@events_bp.route("/events")
def sse():
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive"
        }
    )
```

### `flask_app/routes_action.py`

```python
from flask import Blueprint, request, jsonify
from core.agent_loop import run_agent
from core.task_queue import submit_task, HIGH
from widget.events import push_event

action_bp = Blueprint("action", __name__)

ACTION_PROMPTS = {
    "summarize_emails": "Summarize my action-required emails in 3 sentences",
    "git_pull_all":     "Show git status for all my repos",
    "clear_notifications": None  # handled directly
}

@action_bp.route("/action", methods=["POST"])
def handle_action():
    data   = request.get_json()
    action = data.get("action")

    if action == "clear_notifications":
        push_event({"type": "clear"})
        return jsonify({"result": "Cleared"})

    prompt = ACTION_PROMPTS.get(action)
    if not prompt:
        return jsonify({"result": "Unknown action"}), 400

    result = submit_task(run_agent, prompt, priority=HIGH, timeout=60)
    if "error" in result:
        return jsonify({"result": f"Failed: {result['error']}"}), 500

    return jsonify({"result": result["result"]["response"]})
```

---

## 12. Config & Storage

### `config/settings.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "C:/Users/YourName/projects")

GEMINI_KEYS = [
    k for k in [
        os.getenv("GEMINI_KEY_1"),
        os.getenv("GEMINI_KEY_2"),
        os.getenv("GEMINI_KEY_3"),
        os.getenv("GEMINI_KEY_4"),
        os.getenv("GEMINI_KEY_5"),
    ] if k  # filter out unset keys
]

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN")

if not GEMINI_KEYS:
    raise EnvironmentError("No Gemini API keys found. Check your .env file.")
```

### `data/rules.json` — Personal Email Rules

```json
{
  "always_action_required": [
    "professor@college.edu",
    "hod@department.edu",
    "registrar@college.edu",
    "exam@college.edu",
    "placement@college.edu"
  ],
  "always_ignore": [
    "noreply@linkedin.com",
    "no-reply@",
    "newsletter@",
    "notifications@github.com",
    "mailer-daemon@"
  ],
  "keywords_action": [
    "due date", "deadline", "meeting", "urgent",
    "exam", "result", "attendance", "fee",
    "submission", "assignment", "quiz", "test",
    "internship", "placement", "notice"
  ]
}
```

### `cli.py` — Phase 1 Entry Point

Use this before building any UI. Proves the core works.

```python
# cli.py — run with: python cli.py

from core.agent_loop import run_agent
from core.memory import clear_history
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

print("AI Agent CLI — type 'quit' to exit, 'clear' to reset history\n")

while True:
    try:
        user_input = input("You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        break

    if not user_input:
        continue
    if user_input.lower() == "quit":
        break
    if user_input.lower() == "clear":
        clear_history()
        print("History cleared.\n")
        continue

    result = run_agent(user_input)
    print(f"\nAgent: {result['response']}")

    if result.get("tools_used"):
        print(f"[Tools used: {', '.join(result['tools_used'])}]")
    print()
```

---

## 13. Data Flow

### User Chat (Active)

```
User types → CLI or Chat UI
    ↓
run_agent() or submit_task(priority=HIGH)
    ↓
load_history() → append user message
    ↓
call_gemini() → API Pool (try keys → skip cooldowns → rate limit → next key)
    ↓
Gemini: tool_call or final_text?
    ↓ tool_call
TOOL_REGISTRY[name](**args)
    ↓
result.success == True?
    Yes → append function_response → loop
    No  → append failure message → Gemini explains error → loop or done
    ↓ final_text
save_history() → conversation.json
    ↓
Return {response, tools_used, success}
```

### Background Gmail Check (Passive)

```
APScheduler every 20 min
    ↓
submit_task(priority=LOW) → waits if HIGH task running
    ↓
fetch_emails() → Gmail API → skip cached IDs → parse → cache
    ↓
batch_categorize():
    rules pass → instant, no API
    LLM pass → one batch call, forced JSON response
    ↓
Compare against notification_log.json
    ↓
New action_required emails found?
    Yes → push_event() → SSE stream → widget renders cards instantly
    No  → log "no new emails", done
```

---

## 14. Build Order — CLI First

**Do not build the UI until the core works reliably.**  
Use `cli.py` for the first 2–3 days. Real usage will reveal what's annoying before you spend time on UI.

```
Phase 1 — Core Engine (2–3 days, CLI only)
  ✓ config/settings.py + .env
  ✓ core/api_pool.py
  ✓ core/memory.py
  ✓ core/task_queue.py
  ✓ tools/cmd_tools.py + registry
  ✓ core/agent_loop.py
  ✓ cli.py
  → Test: "make a folder called test-agent in my projects"
  → Test: "find settings.py in my projects"
  → Test: ask something that fails → confirm Gemini tells you what failed
  → Test: exhaust one key → confirm fallback works

Phase 2 — Git Tools (1 day)
  ✓ tools/git_tools.py + registry update
  → Test: "what's the status of [repo]"
  → Test: "what would happen if I push?" (dry run)
  → Test: push without confirming → confirm it asks first
  → Test: push with confirming → confirm it executes

Phase 3 — Gmail (2 days)
  ✓ gmail/auth.py → complete OAuth setup first
  ✓ gmail/fetcher.py + email_cache
  ✓ gmail/categorizer.py + rules.json
  ✓ tools/gmail_tools.py + registry update
  → Test: "show me my action-required emails"
  → Test: check rules are working (add your prof's email, confirm it always shows up)
  → Test: check batch LLM returns valid JSON (add logging for raw response)

Phase 4 — Flask + Chat UI (1 day)
  ✓ flask_app/ (all routes)
  ✓ chat_ui/index.html + chat.js
  → Test: everything from Phases 1–3 via browser chat
  → Test: multi-step query ("check git status and show urgent emails")

Phase 5 — Scheduler + Widget (1–2 days)
  ✓ widget/events.py (bounded SSE queue)
  ✓ flask_app/routes_events.py
  ✓ scheduler/jobs.py (max_instances=1, coalesce=True)
  ✓ widget/popup.html + popup.js
  ✓ widget/tray.py
  ✓ flask_app/routes_action.py
  → Test: trigger Gmail check manually → watch widget update via SSE
  → Test: click widget button → see agent response
  → Test: send chat while Gmail check is queued → confirm chat goes first

Phase 6 — Polish (1 day)
  ✓ setup.py first-run wizard
  ✓ Structured logging everywhere
  ✓ run.py (Flask + tray + scheduler in one command)
  ✓ .gitignore verified
  → Full end-to-end test
  → Use for one real day → note anything annoying → fix it
```

---

## 15. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| LLM | Gemini 1.5 Flash | Fast, cheap, native function calling |
| Backend | Python + Flask | Local, full control, minimal setup |
| Gmail | `google-auth` + `googleapiclient` | Official SDK, handles OAuth |
| Git | `subprocess` + git CLI | Most reliable, no extra library |
| Scheduler | `APScheduler` | Runs inside Python process |
| System Tray | `pystray` | Pure Python, no native dependency |
| Widget Window | `pywebview` | Renders HTML in native OS window |
| Widget Push | Server-Sent Events (SSE) | Simpler than WebSocket, one-way push |
| Priority Queue | `queue.PriorityQueue` | Built-in, thread-safe |
| Credentials | `python-dotenv` | Simple, standard, no overhead |
| Logging | `logging.RotatingFileHandler` | Built-in, reliable, no dependencies |

### `requirements.txt`

```
flask
google-generativeai
google-auth
google-auth-oauthlib
google-api-python-client
apscheduler
pystray
pywebview
pillow
python-dotenv
```

---

## 16. What Goes to LLM vs What Stays Deterministic

This is the most important design decision in the system.

| Task | Approach | Reason |
|------|----------|--------|
| Is email from `professor@college.edu`? | Rules file | 100% reliable, zero cost |
| Does email contain "deadline"? | Keyword match | Deterministic |
| Is this ambiguous email action-required? | LLM (batch) | Only option |
| Run `git status` | subprocess | No reasoning needed |
| Make a folder | `os.makedirs` | No reasoning needed |
| Should I push this code? | User confirmation | Agent shouldn't decide |
| Summarize my emails | LLM | Reasoning required |
| What does this commit message mean? | LLM | Reasoning required |
| Which API key to use? | Cooldown check | Deterministic |
| Is this path safe? | `is_relative_to()` | Deterministic |

**Rule of thumb:** If a Python function can answer it correctly 100% of the time, use a Python function.

---

## Final Reminders

- Build CLI first. Use it. Then build UI.
- Every tool must return `{"success": bool, ...}` — no exceptions.
- If a tool fails, Gemini must be told explicitly — never assume success.
- `shell=False` everywhere, always.
- LLM output is never trusted as a command — only as arguments to whitelisted functions.
- If something annoys you twice, fix it or remove it.