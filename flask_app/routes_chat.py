import logging
from flask import Blueprint, request, jsonify, send_from_directory
from core.agent_loop import run_agent
from config.settings import get_base_dir, reset_base_dir, set_base_dir
import os
import json

chat_bp = Blueprint("chat", __name__)

logger = logging.getLogger(__name__)


@chat_bp.route("/")
def index():

    chat_ui_dir = os.path.join(os.path.dirname(__file__), "..", "chat_ui")
    return send_from_directory(chat_ui_dir, "index.html")


@chat_bp.route("/chat", methods=["POST"])
def chat():
    
    data = request.get_json(silent=True)

    # Validate input
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Expected JSON body"}), 400

    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message field is empty"}), 400

    if len(message) > 2000:
        return jsonify({"error": "message too long (max 2000 chars)"}), 400

    # Run agent
    logger.info(f"[Chat] User: {message[:80]}{'...' if len(message) > 80 else ''}")

    try:
        result = run_agent(message)
    except Exception as e:
        logger.error(f"[Chat] Unhandled error in run_agent: {e}", exc_info=True)
        return jsonify({
            "response": "Something went wrong on my end. Check the logs.",
            "tools_used": [],
            "success": False
        }), 500

    logger.info(
        f"[Chat] Done — success={result['success']} "
        f"tools={result.get('tools_used', [])}"
    )

    return jsonify(result), 200


@chat_bp.route("/health")
def health():
    """Quick check that Flask is up — used by wait_for_flask() in run_chat.py."""
    return jsonify({"status": "ok"}), 200


@chat_bp.route("/clear", methods=["POST"])
def clear_chat():
    """Clear the chat history."""
    try:
        conversation_file = os.path.join(os.path.dirname(__file__), "..", "data", "conversation.json")
        
        # Clear the conversation file
        with open(conversation_file, "w") as f:
            json.dump([], f)
        
        logger.info("[Chat] Chat history cleared")
        return jsonify({"status": "cleared"}), 200
    except Exception as e:
        logger.error(f"[Chat] Error clearing conversation: {e}", exc_info=True)
        return jsonify({"error": "Failed to clear chat history"}), 500


@chat_bp.route("/base-dir", methods=["GET", "POST"])
def base_dir():
    """Read or temporarily change the runtime BASE_DIR, like a scoped cd."""
    if request.method == "GET":
        return jsonify({"base_dir": get_base_dir()}), 200

    data = request.get_json(silent=True) or {}
    path = str(data.get("path", "")).strip()

    try:
        if not path:
            return jsonify({"base_dir": get_base_dir()}), 200
        if path.lower() in {"reset", "/"}:
            return jsonify({"base_dir": reset_base_dir(), "reset": True}), 200
        return jsonify({"base_dir": set_base_dir(path), "reset": False}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"[Chat] Error changing base_dir: {e}", exc_info=True)
        return jsonify({"error": "Failed to change base_dir"}), 500
