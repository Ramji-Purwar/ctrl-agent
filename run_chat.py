"""
ctrl-agent — main entry point.

Starts all components:
  1. Flask server (background thread)
  2. APScheduler for Gmail checks (background thread)
  3. System tray icon (background thread)
  4. Chat window + Widget window (pywebview, main thread — blocks until closed)
"""

import threading
import logging
import sys
import time
import webview
from flask_app.app import create_app
from config.settings import FLASK_HOST, FLASK_PORT, SCHEDULER_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# ── Flask ────────────────────────────────────────────────────────
def start_flask(app):
    """Run Flask in a background daemon thread."""
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
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


# ── Window helpers ───────────────────────────────────────────────
_chat_window   = None
_widget_window = None


def show_chat():
    if _chat_window:
        _chat_window.show()
        _chat_window.restore()


def show_widget():
    if _widget_window:
        _widget_window.show()
        _widget_window.restore()


def on_quit():
    """Shutdown everything."""
    from scheduler.jobs import stop_scheduler
    from widget.tray import stop_tray

    stop_scheduler()
    stop_tray()

    if _chat_window:
        try:
            _chat_window.destroy()
        except Exception:
            pass
    if _widget_window:
        try:
            _widget_window.destroy()
        except Exception:
            pass


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.info("Starting ctrl-agent...")

    app = create_app()

    # 1) Flask
    flask_thread = threading.Thread(target=start_flask, args=(app,), daemon=True)
    flask_thread.start()

    try:
        wait_for_flask()
        logging.info(f"Flask ready at http://{FLASK_HOST}:{FLASK_PORT}")
    except RuntimeError as e:
        logging.error(str(e))
        sys.exit(1)

    # 2) Scheduler
    if SCHEDULER_ENABLED:
        try:
            from scheduler.jobs import start_scheduler
            start_scheduler()
        except Exception as e:
            logging.error(f"Scheduler failed to start: {e}", exc_info=True)
    else:
        logging.info("Scheduler disabled.")

    # 3) System tray
    try:
        from widget.tray import start_tray
        from scheduler.jobs import trigger_check_now

        start_tray(
            on_show_widget=show_widget,
            on_show_chat=show_chat,
            on_check_now=trigger_check_now,
            on_quit=on_quit,
        )
    except Exception as e:
        logging.error(f"System tray failed to start: {e}", exc_info=True)

    # 4) pywebview windows
    _chat_window = webview.create_window(
        title="ctrl-agent",
        url=f"http://{FLASK_HOST}:{FLASK_PORT}",
        width=600,
        height=480,
        min_size=(600, 480),
        resizable=True,
    )

    _widget_window = webview.create_window(
        title="ctrl-agent — Tasks",
        url=f"http://{FLASK_HOST}:{FLASK_PORT}/widget",
        width=360,
        height=520,
        min_size=(320, 400),
        resizable=True,
        on_top=True,
    )

    # webview.start() blocks — when all windows close, we exit
    webview.start()

    # Cleanup
    on_quit()
    logging.info("All windows closed. Exiting.")