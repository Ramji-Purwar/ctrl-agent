"""
Each email gets a category:
  "action_required"  — needs your attention
  "ignore"           — safe to skip
  "info"             — FYI, no action needed
"""

import json
import logging
import time
from pathlib import Path
from core.api_pool import call_llm
from config.settings import GMAIL_RULES_FILE

RULES_FILE = Path(GMAIL_RULES_FILE)

_DEFAULT_RULES = {
    "always_action_required": [],
    "always_ignore": [
        "noreply@",
        "no-reply@",
        "newsletter@",
        "notifications@github.com",
        "mailer-daemon@",
    ],
    "keywords_action": [
        "due date", "deadline", "meeting", "urgent",
        "exam", "result", "attendance", "fee",
        "submission", "assignment", "quiz", "test",
        "internship", "placement", "notice",
    ],
}


# ---------------------------------------------------------------------------
# Rules loading
# ---------------------------------------------------------------------------

def _load_rules() -> dict:
    try:
        if RULES_FILE.exists():
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"[Gmail][Categorizer] Could not load rules.json: {e} — using defaults.")
    return _DEFAULT_RULES


# ---------------------------------------------------------------------------
# Rules-based pass (deterministic, no LLM)
# ---------------------------------------------------------------------------

def _rules_categorize(email: dict, rules: dict) -> str | None:
    """
    Return a category string if the email matches a rule, else None (→ needs LLM).
    """
    sender = email.get("sender_email", "").lower()

    # Exact sender match — action required
    for addr in rules.get("always_action_required", []):
        if addr.lower() in sender:
            return "action_required"

    # Ignore patterns — substring match (handles "noreply@" prefix patterns)
    for pattern in rules.get("always_ignore", []):
        if pattern.lower() in sender:
            return "ignore"

    # Keyword match in subject + snippet
    text = (email.get("subject", "") + " " + email.get("snippet", "")).lower()
    for kw in rules.get("keywords_action", []):
        if kw.lower() in text:
            return "action_required"

    return None  # ambiguous — needs LLM


# ---------------------------------------------------------------------------
# Batch LLM pass
# ---------------------------------------------------------------------------

_BATCH_SYSTEM_PROMPT = (
    "You are an email classifier. You will receive a JSON array of emails. "
    "For each email, decide if it is: 'action_required', 'info', or 'ignore'. "
    "\n"
    "Rules:\n"
    "- action_required: needs the user to do something (reply, attend, submit, pay, confirm, etc.)\n"
    "- info: useful to know but no action needed (receipts, confirmations, newsletters worth reading)\n"
    "- ignore: promotional, automated, irrelevant\n"
    "\n"
    "Respond ONLY with a valid JSON array. No markdown, no code blocks, no explanation.\n"
    "Each item must be: {\"id\": \"<email_id>\", \"category\": \"<action_required|info|ignore>\"}\n"
    "Return exactly one object per input email, in the same order."
)


def _batch_llm_categorize(emails: list[dict]) -> dict[str, str]:
    """
    Send a batch of ambiguous emails to the LLM. Returns {id: category}.
    Falls back to "info" for any email the LLM doesn't classify.
    """
    if not emails:
        return {}

    # Build compact representations to save tokens
    batch_input = [
        {
            "id":      e["id"],
            "subject": e["subject"],
            "sender":  e["sender_email"],
            "snippet": e["snippet"][:200],
        }
        for e in emails
    ]

    prompt = json.dumps(batch_input, ensure_ascii=False)
    messages = [
        {"role": "system", "content": _BATCH_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    # Retry up to 2 times if the response isn't valid JSON
    for attempt in range(1, 3):
        try:
            response  = call_llm(messages)
            raw_text  = response.choices[0].message.content or ""
            # Strip accidental markdown fences
            clean     = raw_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed    = json.loads(clean)

            result = {}
            for item in parsed:
                eid      = item.get("id")
                category = item.get("category", "info")
                if eid and category in ("action_required", "info", "ignore"):
                    result[eid] = category
                elif eid:
                    result[eid] = "info"

            logging.info(f"[Gmail][Categorizer] LLM classified {len(result)} emails.")
            return result

        except json.JSONDecodeError as e:
            logging.warning(
                f"[Gmail][Categorizer] LLM returned invalid JSON (attempt {attempt}): {e}\n"
                f"Raw: {raw_text[:300]}"
            )
            time.sleep(1)
        except Exception as e:
            logging.error(f"[Gmail][Categorizer] LLM call failed: {e}")
            break

    # Fallback: mark everything as "info" so nothing is silently lost
    logging.warning("[Gmail][Categorizer] LLM categorization failed — defaulting all to 'info'.")
    return {e["id"]: "info" for e in emails}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def categorize_emails(emails: list[dict]) -> list[dict]:
    """
    Categorize a list of parsed emails. Adds a 'category' field to each.

    Returns the same list with 'category' and 'category_source' added.
    category_source is 'rules' or 'llm' — useful for debugging.
    """
    if not emails:
        return []

    rules        = _load_rules()
    needs_llm    = []
    results      = {}

    # Pass 1: rules
    for email in emails:
        cat = _rules_categorize(email, rules)
        if cat:
            results[email["id"]] = ("rules", cat)
        else:
            needs_llm.append(email)

    logging.info(
        f"[Gmail][Categorizer] Rules pass: {len(results)} classified, "
        f"{len(needs_llm)} sent to LLM."
    )

    # Pass 2: batch LLM for ambiguous emails
    if needs_llm:
        llm_results = _batch_llm_categorize(needs_llm)
        for email in needs_llm:
            eid = email["id"]
            cat = llm_results.get(eid, "info")
            results[eid] = ("llm", cat)

    # Attach results to emails
    categorized = []
    for email in emails:
        eid = email["id"]
        source, category = results.get(eid, ("llm", "info"))
        categorized.append({
            **email,
            "category":        category,
            "category_source": source,
        })

    return categorized