const messagesEl  = document.getElementById("messages");
const typingEl    = document.getElementById("typing");
const inputEl     = document.getElementById("input");
const sendBtn     = document.getElementById("send-btn");
const clearBtn    = document.getElementById("clear-btn");
const statusEl    = document.getElementById("status-text");
const emptyEl     = document.getElementById("empty");

let busy = false;

// Auto-resize textarea
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

// Send on Enter (Shift+Enter = newline)
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);
clearBtn.addEventListener("click", clearChat);

// Core send function
async function sendMessage() {
  if (busy) return;

  const text = inputEl.value.trim();
  if (!text) return;

  // clear input
  inputEl.value = "";
  inputEl.style.height = "auto";

  // hide empty state on first message
  if (emptyEl) emptyEl.remove();

  appendMessage("user", text);
  setBusy(true);

  try {
    const result = await callChat(text);
    appendAgentMessage(result);
  } catch (err) {
    appendMessage("error", `Connection error: ${err.message}`);
  } finally {
    setBusy(false);
  }
}

// API call
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

// Render a user or error bubble
function appendMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;

  const label = document.createElement("div");
  label.className = "label";
  label.textContent = role === "user" ? "you" : "error";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  wrap.appendChild(label);
  wrap.appendChild(bubble);

  // insert before typing indicator so typing stays at bottom
  messagesEl.insertBefore(wrap, typingEl);
  scrollToBottom();
}

// Render an agent reply with optional tool trace
function appendAgentMessage(result) {
  const wrap = document.createElement("div");
  wrap.className = `msg agent${result.success ? "" : " error"}`;

  const label = document.createElement("div");
  label.className = "label";
  label.textContent = "agent";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = result.response || "(no response)";

  wrap.appendChild(label);
  wrap.appendChild(bubble);

  // tool trace — only show if tools were actually used
  const tools = result.tools_used || [];
  if (tools.length > 0) {
    const details = document.createElement("details");
    details.className = "tool-trace";

    const summary = document.createElement("summary");
    summary.textContent = `${tools.length} tool${tools.length > 1 ? "s" : ""} used`;

    const list = document.createElement("div");
    list.className = "tools-list";

    tools.forEach((t) => {
      const tag = document.createElement("span");
      tag.className = "tool-tag";
      tag.textContent = t;
      list.appendChild(tag);
    });

    details.appendChild(summary);
    details.appendChild(list);
    wrap.appendChild(details);
  }

  messagesEl.insertBefore(wrap, typingEl);
  scrollToBottom();
}

// UI state helpers
function setBusy(state) {
  busy = state;
  sendBtn.disabled = state;
  inputEl.disabled = state;
  typingEl.classList.toggle("visible", state);
  statusEl.textContent = state ? "thinking…" : "ready";
  if (!state) {
    inputEl.focus();
    scrollToBottom();
  }
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Clear chat history
async function clearChat() {
  if (busy) return;
  
  // Clear messages from UI
  const allMessages = messagesEl.querySelectorAll(".msg");
  allMessages.forEach(msg => msg.remove());
  
  // Show empty state again
  const empty = document.createElement("div");
  empty.id = "empty";
  empty.innerHTML = `
    <div class="big">⌘</div>
    <p>Ask me anything.<br/>git · files · coming soon: gmail</p>
  `;
  messagesEl.appendChild(empty);
  
  // Call backend to clear conversation file
  try {
    const res = await fetch("/clear", { method: "POST" });
    if (!res.ok) {
      console.error("Failed to clear chat history on server");
    }
  } catch (err) {
    console.error("Error clearing chat:", err);
  }
}

// Focus input on load
window.addEventListener("load", () => inputEl.focus());