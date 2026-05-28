import os
from flask import Flask, send_from_directory


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="../chat_ui",
        static_url_path=""
    )

    from flask_app.routes_chat import chat_bp
    app.register_blueprint(chat_bp)

    from flask_app.routes_events import events_bp
    app.register_blueprint(events_bp)

    from flask_app.routes_action import action_bp
    app.register_blueprint(action_bp)

    # Serve widget popup
    widget_dir = os.path.join(os.path.dirname(__file__), "..", "widget")

    @app.route("/widget")
    def widget_page():
        return send_from_directory(widget_dir, "popup.html")

    @app.route("/widget/<path:filename>")
    def widget_static(filename):
        return send_from_directory(widget_dir, filename)

    return app