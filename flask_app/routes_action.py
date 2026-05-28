import logging
from flask import Blueprint, request, jsonify

from widget.events import push_event

action_bp = Blueprint("action", __name__)

logger = logging.getLogger(__name__)


@action_bp.route("/action", methods=["POST"])
def handle_action():
    """
    Handle widget action buttons.
    Supported actions: check_now, summarize_emails, clear_notifications.
    """
    data   = request.get_json(silent=True) or {}
    action = data.get("action", "").strip()

    if not action:
        return jsonify({"error": "Missing 'action' field"}), 400

    # ── Clear notifications ────────────────────────────────────────
    if action == "clear_notifications":
        push_event({"type": "clear"})
        return jsonify({"result": "Cleared", "success": True})

    # ── Check now ──────────────────────────────────────────────────
    if action == "check_now":
        try:
            from scheduler.jobs import trigger_check_now
            trigger_check_now()
            return jsonify({"result": "Check complete", "success": True})
        except Exception as e:
            logger.error(f"[Action] check_now failed: {e}", exc_info=True)
            return jsonify({"result": f"Check failed: {e}", "success": False}), 500

    # ── Summarize emails ───────────────────────────────────────────
    if action == "summarize_emails":
        try:
            from core.agent_loop import run_agent
            result = run_agent("Summarize my action-required emails in 3-4 sentences.")
            return jsonify({
                "result":  result.get("response", "No response"),
                "success": result.get("success", False),
            })
        except Exception as e:
            logger.error(f"[Action] summarize_emails failed: {e}", exc_info=True)
            return jsonify({"result": f"Failed: {e}", "success": False}), 500

    return jsonify({"error": f"Unknown action: {action}"}), 400
