const outputEl = document.getElementById("output");
const thinkingEl = document.getElementById("thinking");
const inputEl = document.getElementById("input");
const clearBtn = document.getElementById("clear-btn");

let busy = false;

// Command history — like a real shell
const history = [];
let historyIdx = -1;      // -1 = not browsing history
let pendingInput = "";    // saves what the user was typing before navigating history

// Auto-resize textarea as user types
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

// Enter sends, Up/Down navigates history, Shift+Enter is newline
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleInput();
    return;
  }

  if (e.key === "ArrowUp") {
    e.preventDefault();
    if (history.length === 0) return;
    // Save current input before we start browsing
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
});

function setInput(val) {
  inputEl.value = val;
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  // Move cursor to end
  requestAnimationFrame(() => {
    inputEl.selectionStart = inputEl.selectionEnd = inputEl.value.length;
  });
}

clearBtn.addEventListener("click", clearTerminal);

// ── Main input handler ──────────────────────────────────────────
async function handleInput() {
  if (busy) return;

  const text = inputEl.value.trim();
  if (!text) return;

  // Push to history (skip duplicates at the top)
  if (history[0] !== text) history.unshift(text);
  historyIdx = -1;
  pendingInput = "";

  inputEl.value = "";
  inputEl.style.height = "auto";

  // Intercept local commands — never hit the LLM
  if (text.toLowerCase() === "clear") {
    clearTerminal();
    return;
  }

  if (text.toLowerCase() === "help") {
    printUser(text);
    printAgent("commands:\n  clear       clear the terminal\n  help        show this message\n  <anything>  sent to the agent");
    printSpacer();
    return;
  }

  printUser(text);
  setBusy(true);

  try {
    const result = await callChat(text);
    printAgent(result.response || "(no response)");
    if ((result.tools_used || []).length > 0) {
      printToolTrace(result.tools_used);
    }
  } catch (err) {
    printError(err.message);
  } finally {
    setBusy(false);
    printSpacer();
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

// ── Print helpers ───────────────────────────────────────────────
function printUser(text) {
  const el = document.createElement("div");
  el.className = "line user";
  el.textContent = text;
  outputEl.insertBefore(el, thinkingEl);
  scrollToBottom();
}

function printAgent(text) {
  // Split on newlines and print each as its own line
  const lines = text.split("\n");
  lines.forEach((line) => {
    const el = document.createElement("div");
    el.className = "line agent";
    el.textContent = line;
    outputEl.insertBefore(el, thinkingEl);
  });
  scrollToBottom();
}

function printError(text) {
  const el = document.createElement("div");
  el.className = "line error";
  el.textContent = text;
  outputEl.insertBefore(el, thinkingEl);
  scrollToBottom();
}

function printSpacer() {
  const el = document.createElement("div");
  el.className = "line spacer";
  outputEl.insertBefore(el, thinkingEl);
}

function printToolTrace(tools) {
  const details = document.createElement("details");
  details.className = "tool-trace";

  const summary = document.createElement("summary");
  summary.textContent = `tools: ${tools.join(", ")}`;

  const list = document.createElement("div");
  list.className = "tools-list";
  tools.forEach((t) => {
    const item = document.createElement("div");
    item.className = "tool-item";
    item.textContent = t;
    list.appendChild(item);
  });

  details.appendChild(summary);
  details.appendChild(list);
  outputEl.insertBefore(details, thinkingEl);
  scrollToBottom();
}

// ── UI state ────────────────────────────────────────────────────
function setBusy(state) {
  busy = state;
  inputEl.disabled = state;
  thinkingEl.classList.toggle("visible", state);
  if (!state) {
    inputEl.focus();
    scrollToBottom();
  }
}

function scrollToBottom() {
  outputEl.scrollTop = outputEl.scrollHeight;
}

// ── Clear — local only, also calls backend to wipe conversation ──
async function clearTerminal() {
  // Remove all output lines except #boot and #thinking
  const lines = outputEl.querySelectorAll(".line, .tool-trace");
  lines.forEach((el) => el.remove());

  // Wipe history — up arrow only sees commands since last clear
  history.length = 0;
  historyIdx = -1;
  pendingInput = "";

  scrollToBottom();
  inputEl.focus();

  // Tell backend to reset conversation history (fire and forget)
  fetch("/clear", { method: "POST" }).catch(() => {});
}

// Focus on load
window.addEventListener("load", () => inputEl.focus());