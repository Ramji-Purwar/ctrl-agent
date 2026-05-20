const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("input");
const sendBtn    = document.getElementById("send-btn");
const clearBtn   = document.getElementById("clear-btn");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");

let busy = false;

// ── Command history ─────────────────────────────────────────────
const history = [];
let historyIdx  = -1;
let pendingInput = "";

// ── Auto-resize textarea ────────────────────────────────────────
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

// ── Keyboard handling ───────────────────────────────────────────
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleInput();
    return;
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    if (!history.length) return;
    if (historyIdx === -1) pendingInput = inputEl.value;
    historyIdx = Math.min(historyIdx + 1, history.length - 1);
    setInput(history[historyIdx]);
    return;
  }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (historyIdx === -1) return;
    historyIdx--;
    setInput(historyIdx === -1 ? pendingInput : history[historyIdx]);
    return;
  }
  if (e.key === "l" && e.ctrlKey) {
    e.preventDefault();
    clearTerminal();
  }
});

sendBtn.addEventListener("click", handleInput);
clearBtn.addEventListener("click", clearTerminal);

function setInput(val) {
  inputEl.value = val;
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  requestAnimationFrame(() => {
    inputEl.selectionStart = inputEl.selectionEnd = inputEl.value.length;
  });
}

// ── Main handler ────────────────────────────────────────────────
async function handleInput() {
  if (busy) return;
  const text = inputEl.value.trim();
  if (!text) return;

  // History
  if (history[0] !== text) history.unshift(text);
  historyIdx  = -1;
  pendingInput = "";

  inputEl.value = "";
  inputEl.style.height = "auto";

  // Local commands — never touch the LLM
  if (text.toLowerCase() === "clear") {
    clearTerminal();
    return;
  }

  if (text.toLowerCase() === "help") {
    appendGroup(text, "commands:\n  clear       clear the terminal\n  help        show this message\n  cd          show current directory\n  cd <path>   change directory inside default base\n  cd ..       go up one directory\n  cd /        return to default base\n  <anything>  sent to the agent", [], false);
    return;
  }

  if (isCdCommand(text)) {
    const group = appendGroupShell(text);
    setBusy(true);
    try {
      const path = parseCdCommand(text);
      const result = await setBaseDir(path);
      finalizeGroup(group, result.base_dir, [], true);
    } catch (err) {
      finalizeGroup(group, err.message, [], false);
    } finally {
      setBusy(false);
    }
    return;
  }

  // Show prompt line + thinking spinner
  const group = appendGroupShell(text);
  setBusy(true);

  try {
    const result = await callChat(text);
    finalizeGroup(group, result.response || "(no response)", result.tools_used || [], result.success !== false);
  } catch (err) {
    finalizeGroup(group, err.message, [], false);
  } finally {
    setBusy(false);
  }
}

// ── API ─────────────────────────────────────────────────────────
async function callChat(message) {
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function setBaseDir(path) {
  const res = await fetch("/base-dir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

// ── Render helpers ───────────────────────────────────────────────

// Creates a group with prompt + thinking indicator; returns the group el
function appendGroupShell(cmd) {
  const group = document.createElement("div");
  group.className = "msg-group";

  const promptLine = document.createElement("div");
  promptLine.className = "prompt-line";
  promptLine.innerHTML = `<span class="prompt-sym">›</span><span class="prompt-cmd">${escHtml(cmd)}</span>`;

  const thinking = document.createElement("div");
  thinking.className = "thinking";
  thinking.innerHTML = `
    <div class="thinking-dots"><span></span><span></span><span></span></div>
    <span class="thinking-label">agent is thinking…</span>
  `;

  group.appendChild(promptLine);
  group.appendChild(thinking);
  messagesEl.appendChild(group);
  scrollToBottom();
  return group;
}

// Replaces thinking with final response + tool pills
function finalizeGroup(group, responseText, tools, success) {
  // Remove thinking
  const thinking = group.querySelector(".thinking");
  if (thinking) thinking.remove();

  const block = document.createElement("div");
  block.className = "response-block";

  const textEl = document.createElement("div");
  textEl.className = success ? "response-text" : "response-text error-text";
  textEl.textContent = responseText;
  block.appendChild(textEl);

  if (tools.length > 0) {
    const row = document.createElement("div");
    row.className = "tool-row";

    const label = document.createElement("span");
    label.className = "tool-label";
    label.textContent = "tools";
    row.appendChild(label);

    tools.forEach((t) => {
      const pill = document.createElement("span");
      pill.className = `tool-pill ${toolClass(t)}`;
      pill.innerHTML = `<i class="ti ${toolIcon(t)}" aria-hidden="true"></i> ${escHtml(t)}`;
      row.appendChild(pill);
    });

    block.appendChild(row);
  } else if (success) {
    // "none" pill for responses that used no tools
    const row = document.createElement("div");
    row.className = "tool-row";
    const label = document.createElement("span");
    label.className = "tool-label";
    label.textContent = "tools";
    row.appendChild(label);
    const pill = document.createElement("span");
    pill.className = "tool-pill none";
    pill.innerHTML = `<i class="ti ti-brain" aria-hidden="true"></i> none`;
    row.appendChild(pill);
    block.appendChild(row);
  }

  group.appendChild(block);
  scrollToBottom();
}

// Simple version for local commands (help etc.)
function appendGroup(cmd, responseText, tools, success) {
  const group = appendGroupShell(cmd);
  finalizeGroup(group, responseText, tools, success);
}

// ── Tool pill styling ────────────────────────────────────────────
function toolClass(name) {
  const n = name.toLowerCase();
  if (n.includes("read") || n.includes("find") || n.includes("search") || n.includes("list")) return "info";
  return "success";
}

function toolIcon(name) {
  const n = name.toLowerCase();
  if (n.includes("git"))    return "ti-brand-git";
  if (n.includes("file") || n.includes("read")) return "ti-file";
  if (n.includes("find") || n.includes("search")) return "ti-search";
  if (n.includes("run") || n.includes("exec") || n.includes("bash") || n.includes("shell")) return "ti-terminal";
  if (n.includes("write") || n.includes("create")) return "ti-file-plus";
  if (n.includes("folder") || n.includes("dir")) return "ti-folder";
  if (n.includes("open")) return "ti-external-link";
  return "ti-tool";
}

// ── UI state ─────────────────────────────────────────────────────
function setBusy(state) {
  busy = state;
  inputEl.disabled = state;
  sendBtn.disabled = state;
  if (statusPill) statusPill.classList.toggle("busy", state);
  if (statusText) statusText.textContent = state ? "thinking…" : "ready";
  if (!state) {
    inputEl.focus();
    scrollToBottom();
  }
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Clear ─────────────────────────────────────────────────────────
function clearTerminal() {
  // Remove all message groups
  messagesEl.querySelectorAll(".msg-group").forEach(el => el.remove());

  // Reset history
  history.length = 0;
  historyIdx  = -1;
  pendingInput = "";

  // Tell backend (fire and forget)
  fetch("/clear", { method: "POST" }).catch(() => {});

  inputEl.focus();
}

// ── Util ──────────────────────────────────────────────────────────
function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function isCdCommand(text) {
  return text.toLowerCase() === "cd" || text.toLowerCase().startsWith("cd ");
}

function parseCdCommand(text) {
  return text.slice("cd".length).trim();
}

// Focus on load
window.addEventListener("load", () => inputEl.focus());
