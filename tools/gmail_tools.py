import logging

from gmail.fetcher import fetch_new_emails, get_cached_emails, query_emails
from gmail.categorizer import categorize_emails


def check_emails(category: str = "action_required", limit: int = 10) -> dict:

    try:
        new_emails = fetch_new_emails()

        if not new_emails:
            return {
                "success":   True,
                "emails":    [],
                "total_new": 0,
                "category":  category,
                "message":   "No new emails found.",
            }

        categorized = categorize_emails(new_emails)

        if category == "all":
            filtered = categorized
        else:
            filtered = [e for e in categorized if e.get("category") == category]

        # Trim to limit, most recent last
        filtered = filtered[-limit:]

        return {
            "success":   True,
            "emails":    _format_emails(filtered),
            "total_new": len(new_emails),
            "category":  category,
        }

    except Exception as e:
        logging.error(f"[GmailTool][check_emails] {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def show_recent_emails(limit: int = 10, category: str = "all") -> dict:
    """
    Show emails from the local cache.
    """
    try:
        emails = get_cached_emails(limit=limit * 3)

        if category != "all":
            emails = [e for e in emails if e.get("category") == category]

        emails = emails[-limit:]

        return {
            "success": True,
            "emails":  _format_emails(emails),
            "source":  "cache",
        }

    except Exception as e:
        logging.error(f"[GmailTool][show_recent_emails] {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def summarize_email(email_id: str) -> dict:
    try:
        from gmail.fetcher import _load_cache
        cache = _load_cache()

        if email_id not in cache:
            return {
                "success": False,
                "error":   f"Email ID '{email_id}' not found in cache. Run check_emails first.",
            }

        email = cache[email_id]
        return {"success": True, "email": email}

    except Exception as e:
        logging.error(f"[GmailTool][summarize_email] {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _format_emails(emails: list[dict]) -> list[dict]:
    out = []
    for e in emails:
        out.append({
            "id":       e.get("id", ""),
            "subject":  e.get("subject", "(no subject)"),
            "sender":   e.get("sender_email", e.get("sender", "")),
            "date":     e.get("date", ""),
            "snippet":  e.get("snippet", "")[:300],
            "category": e.get("category", "unknown"),
        })
    return out


def search_emails(query: str, limit: int = 10) -> dict:
    """Search Gmail with any query. Never touches the unread cache."""
    try:
        emails = query_emails(query=query, limit=limit)
        if not emails:
            return {"success": True, "emails": [], "query": query,
                    "message": f"No emails found for query: {query}"}
        return {"success": True, "emails": _format_emails(emails), "query": query}
    except Exception as e:
        logging.error(f"[GmailTool][search_emails] {e}", exc_info=True)
        return {"success": False, "error": str(e)}