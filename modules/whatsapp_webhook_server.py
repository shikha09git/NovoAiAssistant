"""
Lightweight webhook receiver for Twilio WhatsApp inbound messages.
Run: python -m modules.whatsapp_webhook_server
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from modules.whatsapp_mod import WhatsAppModule


class _WebhookHandler(BaseHTTPRequestHandler):
    module = WhatsAppModule()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length).decode("utf-8", errors="ignore")
        form = parse_qs(payload)
        from_number = form.get("From", [""])[0]
        body = form.get("Body", [""])[0]

        if from_number or body:
            self.module.save_incoming(from_number, body)
            print(f"[WhatsApp Webhook] Saved message from {from_number}")

        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(b"<Response></Response>")

    def log_message(self, fmt, *args):
        return


def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), _WebhookHandler)
    print(f"[WhatsApp Webhook] Listening on http://{host}:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
