// ── DOM refs ────────────────────────────────────────────────────
const emailList      = document.getElementById("email-list");
const emptyState     = document.getElementById("empty-state");
const connDot        = document.getElementById("connection-dot");
const connLabel      = document.getElementById("connection-label");
const lastCheckText  = document.getElementById("last-check-text");
const emailCountText = document.getElementById("email-count-text");
const summaryArea    = document.getElementById("summary-area");
const summaryText    = document.getElementById("summary-text");
const summaryClose   = document.getElementById("summary-close");

// ── State ───────────────────────────────────────────────────────
let emails = [];
let source = null;

// ── SSE connection ──────────────────────────────────────────────
function connectSSE() {
  if (source) {
    try { source.close(); } catch (_) {}
  }

  source = new EventSource("/events");

  source.onopen = () => {
    setConnection("connected", "connected");
  };

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleEvent(data);
    } catch (e) {
      console.error("[Widget] Bad SSE data:", e);
    }
  };

  source.onerror = () => {
    setConnection("error", "reconnecting…");
    // EventSource will auto-reconnect
  };
}

// ── Event handler ───────────────────────────────────────────────
function handleEvent(data) {
  switch (data.type) {

    case "new_emails":
      addEmails(data.emails || []);
      break;

    case "remove_email":
      if (data.email_id) {
        emails = emails.filter(e => e.id !== data.email_id);
        renderEmails();
      }
      break;

    case "check_started":
      setConnection("checking", "checking…");
      break;

    case "check_done":
      setConnection("connected", "connected");
      if (data.time) {
        lastCheckText.textContent = formatTime(data.time);
      }
      break;

    case "auth_error":
      setConnection("error", "auth expired");
      showNotification("Gmail auth expired. Open chat and re-authenticate.");
      break;

    case "error":
      showNotification(data.message || "Unknown error");
      break;

    case "clear":
      clearEmails();
      break;

    default:
      console.log("[Widget] Unknown event:", data);
  }
}

// ── Email rendering ─────────────────────────────────────────────
function addEmails(newEmails) {
  // Deduplicate by id
  const existingIds = new Set(emails.map(e => e.id));
  const unique = newEmails.filter(e => !existingIds.has(e.id));

  if (unique.length === 0) return;

  emails = [...emails, ...unique];
  renderEmails();
}

function clearEmails() {
  emails = [];
  renderEmails();
  hideSummary();
}

function renderEmails() {
  // Update count
  emailCountText.textContent = `${emails.length} task${emails.length !== 1 ? "s" : ""}`;

  // Clear list
  emailList.innerHTML = "";

  if (emails.length === 0) {
    emailList.innerHTML = `
      <div id="empty-state">
        <i class="ti ti-inbox-off"></i>
        <p>No action items yet</p>
        <span>Emails requiring your attention will appear here</span>
      </div>
    `;
    return;
  }

  // Build a bullet-point list (newest first)
  const ul = document.createElement("ul");
  ul.className = "task-list";

  const sorted = [...emails].reverse();
  sorted.forEach((email, idx) => {
    const li = document.createElement("li");
    li.className = "task-item";
    li.style.animationDelay = `${idx * 0.03}s`;

    const dateStr = email.date ? formatEmailDate(email.date) : "";
    const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${encodeURIComponent(email.id)}`;

    // Extract short sender name (before @)
    const senderShort = (email.sender || "unknown").split("@")[0];

    li.innerHTML = `
      <span class="task-bullet">•</span>
      <a class="task-link" href="${gmailUrl}" target="_blank" title="Open in Gmail">
        <span class="task-subject">${escHtml(email.subject || "(no subject)")}</span>
        <span class="task-meta">
          <span class="task-sender">${escHtml(senderShort)}</span>
          ${dateStr ? `<span class="task-sep">·</span><span class="task-date">${escHtml(dateStr)}</span>` : ""}
        </span>
      </a>
      <button class="task-remove-btn" data-id="${email.id}" title="Mark as Done (Remove task)">
        <i class="ti ti-check"></i>
      </button>
      <a class="task-open" href="${gmailUrl}" target="_blank" title="Open in Gmail">
        <i class="ti ti-external-link"></i>
      </a>
    `;

    ul.appendChild(li);
  });

  emailList.appendChild(ul);

  // Bind individual remove buttons
  emailList.querySelectorAll(".task-remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const emailId = btn.dataset.id;
      triggerRemove(emailId, btn);
    });
  });
}

// ── Action buttons ──────────────────────────────────────────────
document.querySelectorAll(".action-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const action = btn.dataset.action;
    if (!action || btn.disabled) return;
    triggerAction(action, btn);
  });
});

async function triggerAction(action, btn) {
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
      showSummary(data.result);
    }

    if (action === "clear_notifications") {
      clearEmails();
    }

  } catch (err) {
    console.error(`[Widget] Action '${action}' failed:`, err);
    showNotification(`Action failed: ${err.message}`);
  } finally {
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

async function triggerRemove(emailId, btn) {
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
      console.error("[Widget] Remove failed:", data.error || "Unknown error");
      showNotification(data.error || "Failed to remove task");
      btn.disabled = false;
      btn.style.opacity = 1.0;
    } else {
      emails = emails.filter(e => e.id !== emailId);
      renderEmails();
    }
  } catch (err) {
    console.error("[Widget] Remove failed:", err);
    showNotification(`Failed to remove task: ${err.message}`);
    btn.disabled = false;
    btn.style.opacity = 1.0;
  }
}

// ── Summary panel ───────────────────────────────────────────────
function showSummary(text) {
  summaryText.textContent = text;
  summaryArea.classList.remove("hidden");
}

function hideSummary() {
  summaryArea.classList.add("hidden");
  summaryText.textContent = "";
}

summaryClose.addEventListener("click", hideSummary);

// ── Notifications (in-widget) ───────────────────────────────────
function showNotification(msg) {
  const notice = document.createElement("div");
  notice.className = "notice-bar";
  notice.innerHTML = `
    <i class="ti ti-alert-triangle"></i>
    <span>${escHtml(msg)}</span>
  `;
  emailList.prepend(notice);

  setTimeout(() => {
    if (notice.parentNode) notice.remove();
  }, 10000);
}

// ── Connection indicator ────────────────────────────────────────
function setConnection(state, label) {
  connDot.className = "";
  connDot.classList.add(state);
  connLabel.textContent = label;
}

// ── Utilities ───────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatTime(isoString) {
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
connectSSE();
