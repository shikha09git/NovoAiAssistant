"""
core/tray.py â€” System tray icon (Windows/macOS/Linux)
Shows mic icon in taskbar. Click = trigger Nova.
"""

import threading
from PIL import Image, ImageDraw
import pystray


def _make_icon(color="#5B6EF5"):
    """Draw a simple mic icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Mic body
    d.rounded_rectangle([22, 4, 42, 36], radius=10, fill=color)
    # Mic stand arc
    d.arc([14, 22, 50, 50], start=0, end=180, fill=color, width=4)
    # Stand stem
    d.line([32, 50, 32, 58], fill=color, width=4)
    # Base
    d.line([24, 58, 40, 58], fill=color, width=4)
    return img


def run_tray(agent):
    """Start the system tray icon. Runs in its own thread."""

    def on_listen(icon, item):
        threading.Thread(target=_manual_trigger, args=(agent,), daemon=True).start()

    def on_quit(icon, item):
        agent.listening = False
        icon.stop()

    def _manual_trigger(agent):
        agent.speak("Listening...")
        text = agent.listen_once(timeout=10)
        if text:
            agent.handle_command(text)
        else:
            agent.speak("Kuch suna nahi. Please try again.")

    menu = pystray.Menu(
        pystray.MenuItem("ðŸŽ™ Listen now", on_listen, default=True),
        pystray.MenuItem("Quit Nova", on_quit)
    )

    icon = pystray.Icon(
        name="Nova",
        icon=_make_icon(),
        title="Nova â€” AI Voice Agent",
        menu=menu
    )
    icon.run()
