"""
HTTP server for the Now Playing overlay.

Serves static files with no-cache headers and handles settings save/load.

Usage:
    python server.py          # serves on http://127.0.0.1:8000
    python server.py 9000     # custom port
"""

import http.server
import json
import os
import sys
from functools import partial

MAX_SETTINGS_SIZE = 100_000  # 100 KB

try:
    _port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not (1 <= _port_arg <= 65535):
        print(f"ERROR: Port must be between 1 and 65535, got {_port_arg}")
        sys.exit(1)
    PORT = _port_arg
except ValueError:
    print(f"ERROR: Port must be a number, got '{sys.argv[1]}'")
    sys.exit(1)

# When frozen by PyInstaller, __file__ points to a temp directory.
# The actual files live next to the .exe.
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(ROOT, "settings.json")
JSON_FILE = os.path.join(ROOT, "nowplaying.json")

ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{_port_arg}",
    f"http://localhost:{_port_arg}",
}

os.chdir(ROOT)


class OverlayHandler(http.server.SimpleHTTPRequestHandler):
    """Static file server with no-cache headers + settings save endpoint."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/status" or self.path.startswith("/api/status?"):
            self._handle_status()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/save-settings":
            self._handle_save_settings()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_save_settings(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0 or length > MAX_SETTINGS_SIZE:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"Invalid payload size"}')
                return

            body = self.rfile.read(length)
            data = json.loads(body)

            if not isinstance(data, dict):
                raise ValueError("Settings must be a JSON object")

            # Write atomically
            tmp = SETTINGS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, SETTINGS_FILE)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def _handle_status(self):
        try:
            result = {"server": True, "port": PORT}

            if os.path.isfile(JSON_FILE):
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    np = json.load(f)
                result["extractor"] = True
                result["nowplaying"] = np
            else:
                result["extractor"] = False
                result["nowplaying"] = None

            cover_path = os.path.join(ROOT, "cover.jpg")
            result["hasCover"] = os.path.isfile(cover_path)
            result["hasSettings"] = os.path.isfile(SETTINGS_FILE)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def log_message(self, fmt, *args):
        pass  # keep console clean


def main():
    handler = partial(OverlayHandler, directory=ROOT)
    server = http.server.HTTPServer(("127.0.0.1", PORT), handler)
    print(f"HTTP server running on http://127.0.0.1:{PORT}")
    print(f"  Overlay      http://127.0.0.1:{PORT}/overlay.html")
    print(f"  Settings     http://127.0.0.1:{PORT}/settings.html")
    print(f"  Diagnostics  http://127.0.0.1:{PORT}/status.html")
    print(f"  Preview      http://127.0.0.1:{PORT}/overlay.html?debug")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
