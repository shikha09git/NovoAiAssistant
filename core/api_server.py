"""
Simple HTTP API for mobile/web clients to use the same Nova core.
Run via main.py (auto-start) or import and call run_api_server(agent).
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def run_api_server(agent, host: str = "0.0.0.0", port: int = 8787):
    class _Handler(BaseHTTPRequestHandler):
        def _send_json(self, code: int, payload: dict):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self._send_json(200, {"ok": True})

        def do_POST(self):
            if self.path != "/api/command":
                self._send_json(404, {"ok": False, "error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                body = json.loads(raw) if raw else {}
                text = (body.get("text") or "").strip()
                if not text:
                    self._send_json(400, {"ok": False, "error": "Missing text"})
                    return
                result = agent.process_text(text, speak_out=False, require_confirmation=False)
                self._send_json(200, result)
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)})

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"[API] Nova API listening on http://{host}:{port}/api/command")
    server.serve_forever()
