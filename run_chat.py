"""
ctrl-agent — main entry point.

Starts all components:
  1. Single-instance check (if already running, activate the existing window)
  2. Flask server (background thread)
  3. APScheduler for Gmail checks (background thread)
  4. System tray icon (background thread)
  5. Global hotkey listener Ctrl+Alt+C (background thread)
  6. Chat window (pywebview, main thread — blocks until quit)

Closing the window hides it to system tray.
Only "Quit" from the tray menu terminates the process.
"""

import threading
import logging
import sys
import time
import requests
import webview
from flask_app.app import create_app
from config.settings import FLASK_HOST, FLASK_PORT, SCHEDULER_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

_HOST = FLASK_HOST or "127.0.0.1"
_PORT = int(FLASK_PORT or 5000)


# ── Single-instance check ───────────────────────────────────────
def _is_already_running() -> bool:
    """Ping the health endpoint. If it responds, another instance is alive."""
    try:
        r = requests.get(f"http://{_HOST}:{_PORT}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _activate_existing():
    """Tell the running instance to show its window, then exit."""
    try:
        requests.post(f"http://{_HOST}:{_PORT}/show-chat", timeout=3)
    except Exception:
        pass
    sys.exit(0)


# ── Flask ────────────────────────────────────────────────────────
def start_flask(app):
    """Run Flask in a background daemon thread."""
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(host=_HOST, port=_PORT, threaded=True, use_reloader=False)


def wait_for_flask(timeout=10):
    """Block until Flask is accepting connections, or raise on timeout."""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((_HOST, _PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Flask did not start within {timeout}s")


# ── Window state ─────────────────────────────────────────────────
_chat_window = None
_is_quitting = False


def show_chat():
    """Show and restore the chat window (called from tray / hotkey / second instance)."""
    if _chat_window:
        try:
            _chat_window.show()
            _chat_window.restore()
        except Exception:
            pass


def on_chat_closing():
    """Intercept window close — hide instead of quit."""
    global _is_quitting
    if _is_quitting:
        return True   # allow destruction during quit
    if _chat_window:
        _chat_window.hide()
    return False      # prevent destruction


def on_quit():
    """Shutdown everything."""
    global _is_quitting
    _is_quitting = True

    from scheduler.jobs import stop_scheduler
    from widget.tray import stop_tray

    stop_scheduler()
    stop_tray()

    if _chat_window:
        try:
            _chat_window.destroy()
        except Exception:
            pass


# ── Global hotkey (Ctrl+Alt+C) ───────────────────────────────────
def _register_hotkey():
    """Register a global hotkey using Windows API. Runs in its own thread."""
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32

        MOD_CTRL = 0x0002
        MOD_ALT  = 0x0001
        VK_C     = 0x43
        HOTKEY_ID = 1

        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_ALT, VK_C):
            logging.warning("[Hotkey] Could not register Ctrl+Alt+C (already in use?).")
            return

        logging.info("[Hotkey] Ctrl+Alt+C registered.")

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:   # WM_HOTKEY
                logging.info("[Hotkey] Ctrl+Alt+C pressed — showing chat window.")
                show_chat()

    except Exception as e:
        logging.warning(f"[Hotkey] Failed to set up global hotkey: {e}")


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":

    # 0) Single-instance guard
    if _is_already_running():
        logging.info("Another instance is already running — activating it.")
        _activate_existing()

    logging.info("Starting ctrl-agent...")

    app = create_app()

    # 1) Flask
    flask_thread = threading.Thread(target=start_flask, args=(app,), daemon=True)
    flask_thread.start()

    try:
        wait_for_flask()
        logging.info(f"Flask ready at http://{_HOST}:{_PORT}")
    except RuntimeError as e:
        logging.error(str(e))
        sys.exit(1)

    # Register show_chat callback so /show-chat endpoint can activate the window
    from flask_app.routes_chat import register_show_chat_callback
    register_show_chat_callback(show_chat)

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
            on_show_widget=show_chat,    # "Show Widget" now just shows chat
            on_show_chat=show_chat,
            on_check_now=trigger_check_now,
            on_quit=on_quit,
        )
    except Exception as e:
        logging.error(f"System tray failed to start: {e}", exc_info=True)

    # 4) Global hotkey thread
    if sys.platform == "win32":
        hotkey_thread = threading.Thread(target=_register_hotkey, daemon=True)
        hotkey_thread.start()

    # 5) Single pywebview window (chat only — tasks sidebar is inside)
    _chat_window = webview.create_window(
        title="ctrl-agent",
        url=f"http://{_HOST}:{_PORT}",
        width=700,
        height=520,
        min_size=(600, 480),
        resizable=True,
    )

    _chat_window.events.closing += on_chat_closing

    # webview.start() blocks — when the window is destroyed via Quit, we exit
    webview.start()

    # Cleanup
    on_quit()
    logging.info("All windows closed. Exiting.")