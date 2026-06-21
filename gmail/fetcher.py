import base64
import json
import logging
import re
from pathlib import Path

from gmail.auth import get_gmail_service
from config.settings import GMAIL_CACHE_FILE

CACHE_FILE     = Path(GMAIL_CACHE_FILE)
MAX_RESULTS    = 30
MAX_CACHE_SIZE = 500


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    """Returns {id: parsed_email_dict}."""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"[Gmail][Fetcher] Could not load cache: {e}")
    return {}


def _save_cache(cache: dict):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logging.warning(f"[Gmail][Fetcher] Could not save cache: {e}")


def _trim_cache(cache: dict) -> dict:
    if len(cache) <= MAX_CACHE_SIZE:
        return cache
    # Keep only the most recent MAX_CACHE_SIZE entries
    keys = list(cache.keys())
    for old_key in keys[: len(keys) - MAX_CACHE_SIZE]:
        del cache[old_key]
    return cache


# ---------------------------------------------------------------------------
# Email parsing helpers
# ---------------------------------------------------------------------------

def _decode_body(payload: dict) -> str:
    """Extract plain-text body from a Gmail message payload."""
    # Multipart: recurse into parts
    if "parts" in payload:
        for part in payload["parts"]:
            text = _decode_body(part)
            if text:
                return text
        return ""

    mime = payload.get("mimeType", "")
    if "text/plain" not in mime:
        return ""

    data = payload.get("body", {}).get("data", "")
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return decoded.strip()
    except Exception:
        return ""


def _parse_message(msg: dict) -> dict:
    """Convert a raw Gmail API message into a clean dict."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    subject  = headers.get("subject", "(no subject)")
    sender   = headers.get("from", "")
    date_str = headers.get("date", "")
    msg_id   = msg.get("id", "")
    snippet  = msg.get("snippet", "")
    body     = _decode_body(msg.get("payload", {}))

    # Extract plain email address from "Name <email@domain>" format
    email_match = re.search(r"<(.+?)>", sender)
    sender_email = email_match.group(1).lower() if email_match else sender.lower().strip()

    return {
        "id":           msg_id,
        "subject":      subject,
        "sender":       sender,
        "sender_email": sender_email,
        "date":         date_str,
        "snippet":      snippet,
        "body":         body[:3000],   # cap body to avoid huge LLM prompts
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_new_emails(query: str = "is:unread") -> list[dict]:

    try:
        service = get_gmail_service()
    except Exception as e:
        logging.error(f"[Gmail][Fetcher] Auth failed: {e}")
        return []

    cache = _load_cache()

    # List message IDs
    try:
        result   = service.users().messages().list(
            userId="me", q=query, maxResults=MAX_RESULTS
        ).execute()
        messages = result.get("messages", [])
    except Exception as e:
        logging.error(f"[Gmail][Fetcher] Failed to list messages: {e}")
        return []

    if not messages:
        logging.info("[Gmail][Fetcher] No messages found for query.")
        return []

    new_emails = []
    for msg_ref in messages:
        msg_id = msg_ref["id"]

        if msg_id in cache:
            continue  # already seen

        try:
            full_msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            logging.warning(f"[Gmail][Fetcher] Could not fetch message {msg_id}: {e}")
            continue

        parsed = _parse_message(full_msg)
        cache[msg_id] = parsed
        new_emails.append(parsed)

    cache = _trim_cache(cache)
    _save_cache(cache)

    logging.info(f"[Gmail][Fetcher] Fetched {len(new_emails)} new emails.")
    return new_emails


def get_cached_emails(limit: int = 20) -> list[dict]:
    cache = _load_cache()
    emails = list(cache.values())
    return emails[-limit:]   # most recent are at the end


def query_emails(query: str, limit: int = 10) -> list[dict]:

    try:
        service = get_gmail_service()
    except Exception as e:
        logging.error(f"[Gmail][Fetcher] Auth failed: {e}")
        return []

    try:
        result   = service.users().messages().list(
            userId="me", q=query, maxResults=limit
        ).execute()
        messages = result.get("messages", [])
    except Exception as e:
        logging.error(f"[Gmail][Fetcher] query_emails failed: {e}")
        return []

    emails = []
    for msg_ref in messages:
        try:
            full_msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()
            emails.append(_parse_message(full_msg))
        except Exception as e:
            logging.warning(f"[Gmail][Fetcher] Could not fetch {msg_ref['id']}: {e}")

    logging.info(f"[Gmail][query_emails] query='{query}' returned {len(emails)} results.")
    return emails