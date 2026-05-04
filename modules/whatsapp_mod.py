"""
modules/whatsapp_mod.py - Free WhatsApp helper.
Sends by opening wa.me link and stores local inbox cache for read flow.
"""

import json
import os
import urllib.parse
import webbrowser
from datetime import datetime

INBOX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "whatsapp_inbox.json")


class WhatsAppModule:
    def __init__(self):
        print("[WhatsApp] Free mode active (wa.me links).")

    def send(self, to: str, message: str):
        if not to:
            raise ValueError("Missing recipient number")
        number = to.strip().replace("+", "")
        if not number.startswith("91") and len(number) <= 10:
            number = "91" + number.lstrip("0")
        text = urllib.parse.quote(message or "")
        url = f"https://wa.me/{number}?text={text}"
        webbrowser.open(url)
        print(f"[WhatsApp] Opened send link for {number}")

    def read(self, from_contact: str = "all", limit: int = 10) -> list:
        messages = self._load_inbox()
        if from_contact and from_contact != "all":
            key = from_contact.lower().strip()
            messages = [m for m in messages if key in m.get("from", "").lower()]
        return messages[-limit:]

    def save_incoming(self, from_number: str, body: str):
        messages = self._load_inbox()
        messages.append(
            {
                "from": from_number,
                "body": body,
                "timestamp": datetime.now().isoformat(),
            }
        )
        os.makedirs(os.path.dirname(INBOX_PATH), exist_ok=True)
        with open(INBOX_PATH, "w", encoding="utf-8") as f:
            json.dump(messages[-500:], f, indent=2, ensure_ascii=False)

    def _load_inbox(self) -> list:
        if not os.path.exists(INBOX_PATH):
            return []
        try:
            with open(INBOX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []
