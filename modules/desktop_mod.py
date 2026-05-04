"""
modules/desktop_mod.py - Basic desktop/web control helpers for voice commands.
"""

import shutil
import subprocess
import urllib.parse
import webbrowser
import os


class DesktopModule:
    def __init__(self):
        self.app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "explorer": "explorer.exe",
            "settings": "ms-settings:",
            "cmd": "cmd.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "chorme": "chrome.exe",
            "ms edge": "msedge.exe",
            "edge": "msedge.exe",
            "excel": "excel.exe",
            "microsoft excel": "excel.exe",
            "word": "winword.exe",
            "microsoft word": "winword.exe",
            "powerpoint": "powerpnt.exe",
            "microsoft powerpoint": "powerpnt.exe",
        }

    def open_app(self, app_name: str):
        if not app_name:
            raise ValueError("Missing app name")
        key = app_name.strip().lower().strip("'\"")
        target = self.app_map.get(key, app_name)

        # If a real file/folder path is provided, open it with default app.
        if os.path.exists(target):
            os.startfile(target)  # type: ignore[attr-defined]
            return

        if target.endswith(":"):
            subprocess.Popen(["start", target], shell=True)
            return

        exe = shutil.which(target)
        if exe:
            subprocess.Popen([exe], shell=False)
            return

        # Windows fallback: use Start menu / registered app resolution.
        # Handles commands like "microsoft excel" even without explicit path.
        cmd = f'Start-Process "{target}"'
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            shell=False,
        )

    def open_chrome(self, url: str | None = None):
        chrome = shutil.which("chrome") or shutil.which("chrome.exe")
        if chrome:
            if url:
                subprocess.Popen([chrome, url], shell=False)
            else:
                subprocess.Popen([chrome], shell=False)
            return
        webbrowser.open(url or "https://www.google.com")

    def open_website(self, url: str):
        if not url:
            raise ValueError("Missing website URL")
        cleaned = url.strip()
        if not cleaned.startswith(("http://", "https://")):
            cleaned = "https://" + cleaned
        self.open_chrome(cleaned)

    def search_web(self, query: str):
        q = (query or "").strip()
        if not q:
            raise ValueError("Missing search query")
        encoded = urllib.parse.quote_plus(q)
        self.open_chrome(f"https://www.google.com/search?q={encoded}")

    def open_gmail_inbox(self):
        self.open_chrome("https://mail.google.com/mail/u/0/#inbox")

    def open_gmail_compose(self, to: str = "", subject: str = "", body: str = ""):
        params = {}
        if to:
            params["to"] = to
        if subject:
            params["su"] = subject
        if body:
            params["body"] = body
        query = urllib.parse.urlencode(params)
        base = "https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=1"
        url = f"{base}&{query}" if query else base
        self.open_chrome(url)

    def compose_gmail_with_playwright(self, to: str = "", subject: str = "", body: str = "") -> bool:
        """
        Open Gmail compose in a controlled Playwright Chromium/Chrome window.
        Falls back to regular browser flow when automation is unavailable.
        """
        params = {}
        if to:
            params["to"] = to
        if subject:
            params["su"] = subject
        if body:
            params["body"] = body
        query = urllib.parse.urlencode(params)
        base = "https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=1"
        url = f"{base}&{query}" if query else base

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=False)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Keep browser open for user to review/edit and send manually.
                page.wait_for_timeout(1500)
            return True
        except Exception as e:
            print(f"[Desktop] Gmail Playwright automation unavailable: {e}")
            return False

    def open_gmail_search(self, query: str = "is:unread"):
        q = urllib.parse.quote(query)
        self.open_chrome(f"https://mail.google.com/mail/u/0/#search/{q}")

    def open_whatsapp(self):
        self.open_chrome("https://web.whatsapp.com")

    def open_whatsapp_chat(self, phone: str = "", message: str = ""):
        if not phone:
            self.open_whatsapp()
            return
        number = phone.replace("+", "").strip()
        if not number.startswith("91") and len(number) <= 10:
            number = "91" + number.lstrip("0")
        text = urllib.parse.quote(message or "")
        self.open_chrome(f"https://web.whatsapp.com/send?phone={number}&text={text}")
