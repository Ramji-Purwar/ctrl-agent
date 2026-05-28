"""
Bounded SSE event queue for the desktop widget.

Events are JSON dicts pushed by the scheduler or agent, consumed by the
Flask SSE endpoint, and rendered in the widget UI.

Event types:
    new_emails      — action-required emails found
    check_started   — scheduler began a Gmail check
    check_done      — scheduler finished a Gmail check
    auth_error      — Gmail auth expired
    error           — generic error
    clear           — clear the widget display
"""

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
    while True:
        try:
            event = _event_queue.get(timeout=15)
            yield f"data: {event}\n\n"
        except queue.Empty:
            # Send SSE comment as keepalive (browser ignores comments)
            yield ": keepalive\n\n"
