"""
System tray icon using pystray.

Provides a right-click menu with:
  - Show Widget
  - Show Chat
  - Check Now
  - Quit

The tray icon is a generated purple circle (no external icon file needed).
"""

import threading
import logging
from PIL import Image, ImageDraw

_tray_icon = None
_callbacks = {}


def _create_icon_image(size=64):
    """Generate a simple purple circle icon using Pillow."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer circle — purple
    draw.ellipse(
        [2, 2, size - 3, size - 3],
        fill=(127, 119, 221, 255),        # --purple
        outline=(83, 74, 183, 255),       # --purple-dim
        width=2,
    )

    # Inner dot — teal
    center = size // 2
    r = size // 6
    draw.ellipse(
        [center - r, center - r, center + r, center + r],
        fill=(93, 202, 165, 255),         # --teal
    )

    return img


def start_tray(
    on_show_widget=None,
    on_show_chat=None,
    on_check_now=None,
    on_quit=None,
):
    """
    Start the system tray icon in a background thread.

    Callbacks:
        on_show_widget  — called when "Show Widget" is clicked
        on_show_chat    — called when "Show Chat" is clicked
        on_check_now    — called when "Check Now" is clicked
        on_quit         — called when "Quit" is clicked
    """
    global _tray_icon, _callbacks
    import pystray

    _callbacks = {
        "show_widget": on_show_widget,
        "show_chat":   on_show_chat,
        "check_now":   on_check_now,
        "quit":        on_quit,
    }

    def _on_show_widget(icon, item):
        if _callbacks.get("show_widget"):
            _callbacks["show_widget"]()

    def _on_show_chat(icon, item):
        if _callbacks.get("show_chat"):
            _callbacks["show_chat"]()

    def _on_check_now(icon, item):
        if _callbacks.get("check_now"):
            threading.Thread(target=_callbacks["check_now"], daemon=True).start()

    def _on_quit(icon, item):
        icon.stop()
        if _callbacks.get("quit"):
            _callbacks["quit"]()

    menu = pystray.Menu(
        pystray.MenuItem("Show Widget",  _on_show_widget),
        pystray.MenuItem("Show Chat",    _on_show_chat),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Check Now",    _on_check_now),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit",         _on_quit),
    )

    _tray_icon = pystray.Icon(
        name="ctrl-agent",
        icon=_create_icon_image(),
        title="ctrl-agent",
        menu=menu,
    )

    logging.info("[Tray] Starting system tray icon.")
    # pystray.Icon.run() blocks, so run in a thread
    tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
    tray_thread.start()
    return tray_thread


def stop_tray():
    """Stop the system tray icon."""
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass
        _tray_icon = None
        logging.info("[Tray] Stopped.")
