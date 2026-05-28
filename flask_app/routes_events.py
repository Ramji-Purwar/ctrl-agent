from flask import Blueprint, Response
from widget.events import event_stream

events_bp = Blueprint("events", __name__)


@events_bp.route("/events")
def sse():
    """Server-Sent Events stream for the widget."""
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
