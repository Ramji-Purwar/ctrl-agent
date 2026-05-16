import threading
import logging
import sys
import time
import webview
from flask_app.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

FLASK_PORT = 5000
FLASK_HOST = "127.0.0.1"


def start_flask(app):
    """Run Flask in a background daemon thread."""
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)  # suppress Flask request logs in terminal
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True, use_reloader=False)


def wait_for_flask(timeout=10):
    """Block until Flask is accepting connections, or raise on timeout."""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((FLASK_HOST, FLASK_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Flask did not start within {timeout}s")


if __name__ == "__main__":
    logging.info("Starting AI Agent Chat...")

    app = create_app()

    flask_thread = threading.Thread(target=start_flask, args=(app,), daemon=True)
    flask_thread.start()

    try:
        wait_for_flask()
        logging.info(f"Flask ready at http://{FLASK_HOST}:{FLASK_PORT}")
    except RuntimeError as e:
        logging.error(str(e))
        sys.exit(1)

    # pywebview runs on the main thread — blocks until window is closed
    # When window closes, daemon threads (Flask) die automatically
    window = webview.create_window(
        title="AI Agent",
        url=f"http://{FLASK_HOST}:{FLASK_PORT}",
        width=820,
        height=680,
        min_size=(600, 480),
        resizable=True,
    )
    webview.start()
    logging.info("Window closed. Exiting.")