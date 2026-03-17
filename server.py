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

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
JSON_FILE = os.path.join(ROOT, "nowplaying.json")

os.chdir(ROOT)


class OverlayHandler(http.server.SimpleHTTPRequestHandler):
    """Static file server with no-cache headers + settings save endpoint."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path == "/save-settings":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = json.loads(body)

                # Write atomically
                tmp = SETTINGS_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, SETTINGS_FILE)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode())
        elif self.path == "/api/status":
            try:
                result = {"server": True, "port": PORT}

                # Check if nowplaying.json exists and is recent
                if os.path.isfile(JSON_FILE):
                    with open(JSON_FILE, "r", encoding="utf-8") as f:
                        np = json.load(f)
                    result["extractor"] = True
                    result["nowplaying"] = np
                else:
                    result["extractor"] = False
                    result["nowplaying"] = None

                # Check cover
                cover_path = os.path.join(ROOT, "cover.jpg")
                result["hasCover"] = os.path.isfile(cover_path)

                # Check settings
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
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # keep console clean


def main():
    server = http.server.HTTPServer(("127.0.0.1", PORT), OverlayHandler)
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
