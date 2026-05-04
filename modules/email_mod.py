"""
modules/email_mod.py — Gmail Read / Send / Reply
Uses Gmail API (OAuth2). Run setup.py first to authenticate.
"""

import os
import base64
import re
from pathlib import Path
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://mail.google.com/"]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gmail_token.json")
CREDS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gmail_credentials.json")


class EmailModule:
    def __init__(self):
        self.service = None
        self.browser_profile_dir = os.getenv(
            "NOVA_BROWSER_PROFILE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "data", "browser_profile"),
        )
        self.gmail_auto_send = str(os.getenv("NOVA_GMAIL_AUTO_SEND", "0")).strip().lower() in ("1", "true", "yes", "on")
        self._try_connect()

    @property
    def api_connected(self) -> bool:
        return self.service is not None

    def _try_connect(self):
        try:
            creds = None
            if os.path.exists(TOKEN_PATH):
                creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(CREDS_PATH):
                    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(TOKEN_PATH, "w") as f:
                        f.write(creds.to_json())
                else:
                    print("[Email] No credentials found. Add gmail_credentials.json to data/")
                    return
            self.service = build("gmail", "v1", credentials=creds)
            print("[Email] Gmail connected.")
        except Exception as e:
            print(f"[Email] Connection failed: {e}")

    def send(self, to: str, subject: str, body: str):
        if not self.service:
            raise RuntimeError("Gmail not connected. Run setup first.")
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        self.service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        print(f"[Email] Sent to {to}")

    def reply(self, reply_to_name: str, body: str):
        """Find the latest email from a name and reply to it."""
        if not self.service:
            raise RuntimeError("Gmail not connected.")
        results = self.service.users().messages().list(
            userId="me", q=f"from:{reply_to_name}", maxResults=1
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            raise ValueError(f"No email found from {reply_to_name}")

        msg_data = self.service.users().messages().get(
            userId="me", id=messages[0]["id"], format="metadata"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
        reply_msg = MIMEText(body)
        reply_msg["to"] = headers.get("From", reply_to_name)
        reply_msg["subject"] = "Re: " + headers.get("Subject", "")
        reply_msg["In-Reply-To"] = headers.get("Message-ID", "")
        raw = base64.urlsafe_b64encode(reply_msg.as_bytes()).decode()
        self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": messages[0]["threadId"]}
        ).execute()
        print(f"[Email] Replied to {reply_to_name}")

    def reply_latest(self, body: str, filter_str: str = "in:inbox") -> str:
        """Reply to the latest message in inbox and return recipient."""
        if not self.service:
            raise RuntimeError("Gmail not connected.")
        results = self.service.users().messages().list(
            userId="me", q=filter_str, maxResults=1
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            raise ValueError("No emails found to reply.")

        msg_data = self.service.users().messages().get(
            userId="me", id=messages[0]["id"], format="metadata"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
        from_header = headers.get("From", "")
        subject = headers.get("Subject", "")
        message_id = headers.get("Message-ID", "")

        # Extract plain email from `Name <email@domain.com>` format.
        m = re.search(r"<([^>]+)>", from_header)
        to_addr = m.group(1) if m else from_header

        reply_msg = MIMEText(body or "Thanks, received.")
        reply_msg["to"] = to_addr
        reply_msg["subject"] = "Re: " + subject
        reply_msg["In-Reply-To"] = message_id
        raw = base64.urlsafe_b64encode(reply_msg.as_bytes()).decode()

        self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": messages[0]["threadId"]}
        ).execute()
        print(f"[Email] Replied to latest message from {to_addr}")
        return to_addr

    def read(self, filter_str: str = "is:unread", max_results: int = 5) -> list:
        if not self.service:
            return []
        results = self.service.users().messages().list(
            userId="me", q=filter_str, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        emails = []
        for m in messages:
            data = self.service.users().messages().get(
                userId="me", id=m["id"], format="metadata"
            ).execute()
            headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
            emails.append({
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "id": m["id"],
                "threadId": m["threadId"]
            })
        return emails

    def read_browser(self, max_results: int = 5) -> list:
        """
        Browser-only Gmail inbox reader via Playwright.
        Requires user to be logged in Gmail in persistent browser profile.
        """
        try:
            from playwright.sync_api import sync_playwright

            Path(self.browser_profile_dir).mkdir(parents=True, exist_ok=True)
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.browser_profile_dir,
                    channel="chrome",
                    headless=False,
                )
                page = context.new_page()
                page.goto("https://mail.google.com/mail/u/0/#inbox", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)

                # If not logged in, user must sign in manually once in this profile.
                if "accounts.google.com" in page.url:
                    print("[Email] Browser mode: please login to Gmail once, then retry.")
                    context.close()
                    return []

                rows = page.locator("tr.zA")
                count = min(rows.count(), max_results)
                emails = []
                for i in range(count):
                    row = rows.nth(i)
                    sender = row.locator("span[email], span.yP").first.inner_text(timeout=2000).strip()
                    subject = row.locator("span.bog").first.inner_text(timeout=2000).strip()
                    snippet = row.locator("span.y2").first.inner_text(timeout=2000).strip()
                    emails.append({
                        "from": sender or "Unknown",
                        "subject": subject or "(no subject)",
                        "snippet": snippet,
                        "source": "browser",
                    })
                context.close()
                return emails
        except Exception as e:
            print(f"[Email] Browser read failed: {e}")
            return []

    def reply_latest_browser(self, body: str) -> str:
        """
        Browser-only reply to latest inbox message.
        Opens Gmail thread and prepares/sends reply depending on NOVA_GMAIL_AUTO_SEND.
        """
        try:
            from playwright.sync_api import sync_playwright

            Path(self.browser_profile_dir).mkdir(parents=True, exist_ok=True)
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.browser_profile_dir,
                    channel="chrome",
                    headless=False,
                )
                page = context.new_page()
                page.goto("https://mail.google.com/mail/u/0/#inbox", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)

                if "accounts.google.com" in page.url:
                    context.close()
                    raise RuntimeError("Please login to Gmail once in browser mode.")

                first_row = page.locator("tr.zA").first
                sender = first_row.locator("span[email], span.yP").first.inner_text(timeout=3000).strip()
                first_row.click()
                page.wait_for_timeout(1800)

                # Try modern Gmail reply button first, then generic fallback.
                reply_btn = page.locator("div[aria-label^='Reply'], span:has-text('Reply')").first
                reply_btn.click(timeout=5000)
                page.wait_for_timeout(800)

                editor = page.locator("div[aria-label='Message Body'], div[role='textbox'][aria-label*='Message Body']").first
                editor.click(timeout=5000)
                editor.fill(body or "Thanks, received.")

                if self.gmail_auto_send:
                    send_btn = page.locator("div[aria-label*='Send'][role='button'], span:has-text('Send')").first
                    send_btn.click(timeout=5000)
                    page.wait_for_timeout(1200)
                    context.close()
                    return sender or "latest sender"

                # Keep draft open for manual confirmation.
                return sender or "latest sender"
        except Exception as e:
            raise RuntimeError(f"Browser reply failed: {e}")
