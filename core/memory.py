"""
core/memory.py â€” Persistent memory using SQLite
Stores: interactions, contacts, preferences, notes
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "nova_memory.db")


class Memory:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_text TEXT,
                intent TEXT,
                action_json TEXT
            );
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS contacts (
                name TEXT PRIMARY KEY,
                phone TEXT,
                email TEXT,
                whatsapp TEXT,
                notes TEXT
            );
        """)
        self.conn.commit()

    def save_interaction(self, user_text: str, intent: str, action: dict):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO interactions (timestamp, user_text, intent, action_json) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), user_text, intent, json.dumps(action))
        )
        self.conn.commit()

    def save(self, key: str, value: str):
        c = self.conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?,?,?)",
            (key, value, datetime.now().isoformat())
        )
        self.conn.commit()

    def get(self, key: str) -> str | None:
        c = self.conn.cursor()
        row = c.execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def save_contact(self, name: str, phone: str = None, email: str = None,
                     whatsapp: str = None, notes: str = None):
        c = self.conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO contacts (name, phone, email, whatsapp, notes) VALUES (?,?,?,?,?)",
            (name, phone, email, whatsapp, notes)
        )
        self.conn.commit()

    def get_contact(self, name: str) -> dict | None:
        c = self.conn.cursor()
        row = c.execute(
            "SELECT name, phone, email, whatsapp, notes FROM contacts WHERE name LIKE ?",
            (f"%{name}%",)
        ).fetchone()
        if row:
            return {"name": row[0], "phone": row[1], "email": row[2],
                    "whatsapp": row[3], "notes": row[4]}
        return None

    def get_recent_interactions(self, limit=10) -> list:
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT timestamp, user_text, intent FROM interactions ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"time": r[0], "text": r[1], "intent": r[2]} for r in rows]

    def get_context(self) -> str:
        """Build a short memory context string for the AI prompt."""
        recent = self.get_recent_interactions(5)
        kv = self.conn.execute("SELECT key, value FROM kv_store ORDER BY updated_at DESC LIMIT 10").fetchall()

        lines = []
        if recent:
            lines.append("Recent interactions:")
            for r in recent:
                lines.append(f"  [{r['intent']}] {r['text'][:80]}")
        if kv:
            lines.append("Saved info:")
            for k, v in kv:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "No previous context."

    def close(self):
        self.conn.close()
