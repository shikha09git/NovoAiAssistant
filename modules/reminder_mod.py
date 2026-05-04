"""
modules/reminder_mod.py â€” Voice-set reminders with OS notifications
"""

import threading
import time
import json
import os
import re
from datetime import datetime, timedelta
from plyer import notification  # pip install plyer

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "reminders.json")

# Natural language time keywords (Hindi + English)
TIME_KEYWORDS = {
    "5 minute": 5, "5 min": 5, "paanch minute": 5,
    "10 minute": 10, "10 min": 10, "das minute": 10,
    "15 minute": 15, "aadha ghanta": 30, "half hour": 30,
    "1 ghanta": 60, "1 hour": 60, "ek ghanta": 60,
    "2 ghanta": 120, "2 hours": 120,
    "kal": 1440, "tomorrow": 1440,
}


class ReminderModule:
    def __init__(self):
        self._load()
        self._start_checker()

    def _load(self):
        if os.path.exists(REMINDERS_FILE):
            with open(REMINDERS_FILE) as f:
                self.reminders = json.load(f)
        else:
            self.reminders = []

    def _save(self):
        os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
        with open(REMINDERS_FILE, "w") as f:
            json.dump(self.reminders, f, indent=2)

    def set(self, text: str, time_str: str):
        """Set a reminder. time_str can be natural language or ISO datetime."""
        trigger_at = self._parse_time(time_str)
        reminder = {
            "text": text,
            "trigger_at": trigger_at.isoformat(),
            "done": False
        }
        self.reminders.append(reminder)
        self._save()
        print(f"[Reminder] Set: '{text}' at {trigger_at.strftime('%H:%M, %d %b')}")
        return trigger_at

    def _parse_time(self, time_str: str) -> datetime:
        if not time_str:
            return datetime.now() + timedelta(minutes=5)
        ts = time_str.lower()

        # Dynamic patterns like "1 minute", "30 sec", "2 ghante", "3 hours".
        m = re.search(
            r"(\d+)\s*(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs|ghanta|ghante)",
            ts,
        )
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith(("second", "sec")):
                return datetime.now() + timedelta(seconds=n)
            if unit.startswith(("hour", "hr")) or unit.startswith("ghanta") or unit.startswith("ghante"):
                return datetime.now() + timedelta(hours=n)
            return datetime.now() + timedelta(minutes=n)

        if "ek minute" in ts:
            return datetime.now() + timedelta(minutes=1)
        if "ek ghanta" in ts:
            return datetime.now() + timedelta(hours=1)

        # Check natural language keywords
        for keyword, minutes in TIME_KEYWORDS.items():
            if keyword in ts:
                return datetime.now() + timedelta(minutes=minutes)
        # Try ISO parse
        try:
            return datetime.fromisoformat(time_str)
        except Exception:
            return datetime.now() + timedelta(minutes=10)

    def _start_checker(self):
        def _check():
            while True:
                now = datetime.now()
                changed = False
                for r in self.reminders:
                    if not r["done"] and datetime.fromisoformat(r["trigger_at"]) <= now:
                        self._notify(r["text"])
                        r["done"] = True
                        changed = True
                if changed:
                    self._save()
                time.sleep(30)

        threading.Thread(target=_check, daemon=True).start()

    def _notify(self, text: str):
        try:
            notification.notify(
                title="Nova Reminder",
                message=text,
                app_name="Nova AI",
                timeout=10
            )
        except Exception:
            pass
        print(f"[Reminder] ALERT: {text}")
