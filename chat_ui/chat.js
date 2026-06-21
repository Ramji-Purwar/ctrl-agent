// ── DOM refs (chat) ─────────────────────────────────────────────
const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("input");
const sendBtn    = document.getElementById("send-btn");
const clearBtn   = document.getElementById("clear-btn");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");
const chatPanel  = document.getElementById("chat-panel");

// ── DOM refs (tasks sidebar) ────────────────────────────────────
const tasksSidebar       = document.getElementById("tasks-sidebar");
const tasksToggleBtn     = document.getElementById("tasks-toggle-btn");
const tasksToggleIcon    = document.getElementById("tasks-toggle-icon");
const tasksBadge         = document.getElementById("tasks-badge");
const tasksEmailList     = document.getElementById("tasks-email-list");
const tasksConnDot       = document.getElementById("tasks-connection-dot");
const tasksConnLabel     = document.getElementById("tasks-connection-label");
const tasksLastCheckText = document.getElementById("tasks-last-check-text");
const tasksEmailCountText= document.getElementById("tasks-email-count-text");
const tasksSummaryArea   = document.getElementById("tasks-summary-area");
const tasksSummaryText   = document.getElementById("tasks-summary-text");
const tasksSummaryClose  = document.getElementById("tasks-summary-close");

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
if (clearBtn) clearBtn.addEventListener("click", clearTerminal);

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
  if (n.includes("mail") || n.includes("email")) return "ti-mail";
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


/* ═══════════════════════════════════════════════════════════════
   TASKS SIDEBAR — SSE + rendering
   ═══════════════════════════════════════════════════════════════ */

let taskEmails = [];
let sseSource  = null;

// ── Toggle sidebar ──────────────────────────────────────────────
function toggleTasksSidebar(forceShow) {
  const isHidden = tasksSidebar.classList.contains("hidden");
  const shouldShow = forceShow !== undefined ? forceShow : isHidden;

  if (shouldShow) {
    tasksSidebar.classList.remove("hidden");
    chatPanel.classList.add("hidden");
    tasksToggleBtn.classList.add("active");
    if (tasksToggleIcon) {
      tasksToggleIcon.className = "ti ti-messages";
    }
    tasksToggleBtn.title = "Open Chat";
  } else {
    tasksSidebar.classList.add("hidden");
    chatPanel.classList.remove("hidden");
    tasksToggleBtn.classList.remove("active");
    if (tasksToggleIcon) {
      tasksToggleIcon.className = "ti ti-mail";
    }
    tasksToggleBtn.title = "Open Tasks";
  }
}

if (tasksToggleBtn) {
  tasksToggleBtn.addEventListener("click", () => toggleTasksSidebar());
}

// ── SSE connection ──────────────────────────────────────────────
function connectTasksSSE() {
  if (sseSource) {
    try { sseSource.close(); } catch (_) {}
  }

  sseSource = new EventSource("/events");

  sseSource.onopen = () => {
    setTasksConnection("connected", "connected");
  };

  sseSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleTaskEvent(data);
    } catch (e) {
      console.error("[Tasks] Bad SSE data:", e);
    }
  };

  sseSource.onerror = () => {
    setTasksConnection("error", "reconnecting…");
  };
}

function handleTaskEvent(data) {
  switch (data.type) {
    case "new_emails":
      addTaskEmails(data.emails || []);
      break;
    case "remove_email":
      if (data.email_id) {
        taskEmails = taskEmails.filter(e => e.id !== data.email_id);
        renderTaskEmails();
        updateTaskBadge();
      }
      break;
    case "check_started":
      setTasksConnection("checking", "checking…");
      break;
    case "check_done":
      setTasksConnection("connected", "connected");
      if (data.time && tasksLastCheckText) {
        tasksLastCheckText.textContent = formatTaskTime(data.time);
      }
      break;
    case "auth_error":
      setTasksConnection("error", "auth expired");
      showTaskNotice("Gmail auth expired. Open chat and re-authenticate.");
      break;
    case "error":
      showTaskNotice(data.message || "Unknown error");
      break;
    case "clear":
      clearTaskEmails();
      break;
    default:
      console.log("[Tasks] Unknown event:", data);
  }
}

// ── Email rendering ─────────────────────────────────────────────
function addTaskEmails(newEmails) {
  const existingIds = new Set(taskEmails.map(e => e.id));
  const unique = newEmails.filter(e => !existingIds.has(e.id));
  if (unique.length === 0) return;

  taskEmails = [...taskEmails, ...unique];
  renderTaskEmails();
  updateTaskBadge();
}

function clearTaskEmails() {
  taskEmails = [];
  renderTaskEmails();
  updateTaskBadge();
  hideTaskSummary();
}

function renderTaskEmails() {
  if (!tasksEmailList) return;

  if (tasksEmailCountText) {
    tasksEmailCountText.textContent = `${taskEmails.length} task${taskEmails.length !== 1 ? "s" : ""}`;
  }

  tasksEmailList.innerHTML = "";

  if (taskEmails.length === 0) {
    tasksEmailList.innerHTML = `
      <div id="tasks-empty-state">
        <i class="ti ti-inbox-off"></i>
        <p>No action items yet</p>
        <span>Emails requiring your attention will appear here</span>
      </div>
    `;
    return;
  }

  const ul = document.createElement("ul");
  ul.className = "tasks-list";

  const sorted = [...taskEmails].reverse();
  sorted.forEach((email, idx) => {
    const li = document.createElement("li");
    li.className = "tasks-item";
    li.style.animationDelay = `${idx * 0.03}s`;

    const dateStr = email.date ? formatEmailDate(email.date) : "";
    const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${encodeURIComponent(email.id)}`;
    const senderShort = (email.sender || "unknown").split("@")[0];

    li.innerHTML = `
      <span class="tasks-bullet">•</span>
      <a class="tasks-link" href="${gmailUrl}" target="_blank" title="Open in Gmail">
        <span class="tasks-subject">${escHtml(email.subject || "(no subject)")}</span>
        <span class="tasks-meta">
          <span class="tasks-sender">${escHtml(senderShort)}</span>
          ${dateStr ? `<span class="tasks-sep">·</span><span class="tasks-date">${escHtml(dateStr)}</span>` : ""}
        </span>
      </a>
      <button class="tasks-remove-btn" data-id="${email.id}" title="Mark as Done (Remove task)">
        <i class="ti ti-check"></i>
      </button>
      <a class="tasks-open" href="${gmailUrl}" target="_blank" title="Open in Gmail">
        <i class="ti ti-external-link"></i>
      </a>
    `;

    ul.appendChild(li);
  });

  tasksEmailList.appendChild(ul);

  // Bind individual remove buttons
  tasksEmailList.querySelectorAll(".tasks-remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const emailId = btn.dataset.id;
      triggerTaskRemove(emailId, btn);
    });
  });
}

function updateTaskBadge() {
  if (!tasksBadge) return;
  if (taskEmails.length > 0) {
    tasksBadge.textContent = taskEmails.length;
    tasksBadge.classList.remove("hidden");
  } else {
    tasksBadge.classList.add("hidden");
  }
}

// ── Action buttons ──────────────────────────────────────────────
document.querySelectorAll(".tasks-action-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const action = btn.dataset.action;
    if (!action || btn.disabled) return;
    triggerTaskAction(action, btn);
  });
});

async function triggerTaskAction(action, btn) {
  btn.classList.add("loading");
  btn.disabled = true;

  try {
    const res = await fetch("/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });

    const data = await res.json().catch(() => ({}));

    if (action === "summarize_emails" && data.result) {
      showTaskSummary(data.result);
    }

    if (action === "clear_notifications") {
      clearTaskEmails();
    }

  } catch (err) {
    console.error(`[Tasks] Action '${action}' failed:`, err);
    showTaskNotice(`Action failed: ${err.message}`);
  } finally {
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

async function triggerTaskRemove(emailId, btn) {
  btn.disabled = true;
  btn.style.opacity = 0.5;

  try {
    const res = await fetch("/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "remove_email", email_id: emailId }),
    });

    const data = await res.json().catch(() => ({}));
    if (!data.success) {
      console.error("[Tasks] Remove failed:", data.error || "Unknown error");
      showTaskNotice(data.error || "Failed to remove task");
      btn.disabled = false;
      btn.style.opacity = 1.0;
    } else {
      // Local removal (fallback if SSE delay occurs)
      taskEmails = taskEmails.filter(e => e.id !== emailId);
      renderTaskEmails();
      updateTaskBadge();
    }
  } catch (err) {
    console.error("[Tasks] Remove failed:", err);
    showTaskNotice(`Failed to remove task: ${err.message}`);
    btn.disabled = false;
    btn.style.opacity = 1.0;
  }
}

// ── Summary panel ───────────────────────────────────────────────
function showTaskSummary(text) {
  if (tasksSummaryText) tasksSummaryText.textContent = text;
  if (tasksSummaryArea) tasksSummaryArea.classList.remove("hidden");
}

function hideTaskSummary() {
  if (tasksSummaryArea) tasksSummaryArea.classList.add("hidden");
  if (tasksSummaryText) tasksSummaryText.textContent = "";
}

if (tasksSummaryClose) {
  tasksSummaryClose.addEventListener("click", hideTaskSummary);
}

// ── Notifications (in-sidebar) ──────────────────────────────────
function showTaskNotice(msg) {
  if (!tasksEmailList) return;
  const notice = document.createElement("div");
  notice.className = "tasks-notice-bar";
  notice.innerHTML = `
    <i class="ti ti-alert-triangle"></i>
    <span>${escHtml(msg)}</span>
  `;
  tasksEmailList.prepend(notice);
  setTimeout(() => { if (notice.parentNode) notice.remove(); }, 10000);
}

// ── Connection indicator ────────────────────────────────────────
function setTasksConnection(state, label) {
  if (tasksConnDot) {
    tasksConnDot.className = "";
    tasksConnDot.classList.add(state);
  }
  if (tasksConnLabel) tasksConnLabel.textContent = label;
}

// ── Utilities ───────────────────────────────────────────────────
function formatTaskTime(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return isoString;
  }
}

function formatEmailDate(dateStr) {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;

    if (diff < 60000)       return "now";
    if (diff < 3600000)     return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000)    return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000)   return `${Math.floor(diff / 86400000)}d ago`;
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

// ── Init ────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  inputEl.focus();
  connectTasksSSE();
});
