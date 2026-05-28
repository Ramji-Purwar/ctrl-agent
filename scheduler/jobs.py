"""
APScheduler-based background Gmail check.

Runs a recurring job that:
1. Fetches new unread emails via Gmail API
2. Categorizes them (rules-first, then LLM batch)
3. Pushes action-required emails to the widget via SSE events

max_instances=1 + coalesce=True prevents overlapping runs.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import SCHEDULER_INTERVAL_MINUTES, SCHEDULER_ENABLED
from widget.events import push_event

_scheduler = None


def gmail_check_job():
    """Fetch, categorize, and push action-required emails to the widget."""
    logging.info("[Scheduler] Gmail check started.")
    push_event({"type": "check_started", "time": datetime.now().isoformat()})

    try:
        from gmail.fetcher import fetch_new_emails
        from gmail.categorizer import categorize_emails

        new_emails = fetch_new_emails()

        if not new_emails:
            logging.info("[Scheduler] No new emails.")
            push_event({
                "type":  "check_done",
                "time":  datetime.now().isoformat(),
                "count": 0,
            })
            return

        categorized = categorize_emails(new_emails)
        action_required = [e for e in categorized if e.get("category") == "action_required"]

        if action_required:
            push_event({
                "type":   "new_emails",
                "emails": [
                    {
                        "id":       e.get("id", ""),
                        "subject":  e.get("subject", "(no subject)"),
                        "sender":   e.get("sender_email", e.get("sender", "")),
                        "date":     e.get("date", ""),
                        "snippet":  e.get("snippet", "")[:200],
                        "category": e.get("category", "unknown"),
                    }
                    for e in action_required
                ],
                "count": len(action_required),
                "time":  datetime.now().isoformat(),
            })
            logging.info(f"[Scheduler] {len(action_required)} action-required emails pushed to widget.")
        else:
            logging.info("[Scheduler] New emails found but none action-required.")

        push_event({
            "type":  "check_done",
            "time":  datetime.now().isoformat(),
            "count": len(action_required),
        })

    except FileNotFoundError as e:
        logging.error(f"[Scheduler] Gmail not configured: {e}")
        push_event({"type": "auth_error", "message": str(e)})

    except Exception as e:
        logging.error(f"[Scheduler] Gmail check failed: {e}", exc_info=True)
        push_event({"type": "error", "message": f"Gmail check failed: {e}"})


def start_scheduler():
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler

    if not SCHEDULER_ENABLED:
        logging.info("[Scheduler] Disabled via SCHEDULER_ENABLED=false.")
        return

    if _scheduler and _scheduler.running:
        logging.warning("[Scheduler] Already running.")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        gmail_check_job,
        trigger="interval",
        minutes=SCHEDULER_INTERVAL_MINUTES,
        id="gmail_check",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    logging.info(
        f"[Scheduler] Started — checking Gmail every {SCHEDULER_INTERVAL_MINUTES} minutes."
    )


def stop_scheduler():
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logging.info("[Scheduler] Stopped.")
        _scheduler = None


def trigger_check_now():
    """Run a Gmail check immediately (outside the normal schedule)."""
    logging.info("[Scheduler] Manual check triggered.")
    gmail_check_job()
