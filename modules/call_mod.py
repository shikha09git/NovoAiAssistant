"""
modules/call_mod.py - Free call helper (no Twilio).
Opens OS dialer (where supported) or prints the number.
"""

import webbrowser


class CallModule:
    def __init__(self):
        pass

    def dial(self, to: str):
        if not to:
            raise ValueError("Missing phone number")
        if not to.startswith("+"):
            to = "+91" + to.lstrip("0")
        try:
            webbrowser.open(f"tel:{to}")
        except Exception:
            pass
        print(f"[Call] Dial helper opened for {to}")
