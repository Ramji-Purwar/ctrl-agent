from flask import Flask

def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="../chat_ui",
        static_url_path=""
    )

    from flask_app.routes_chat import chat_bp
    app.register_blueprint(chat_bp)

    return app