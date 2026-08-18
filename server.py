"""Local HTTP server and control API for Now Playing."""

from __future__ import annotations

import http.server
import json
import mimetypes
import os
import sys
import threading
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from paths import DATA_DIR, LOG_DIR, RESOURCE_DIR
from presets import load_presets, save_presets
from settings_schema import SETTINGS_FILE, initialize_settings, load_settings, save_settings
from version import __version__


MAX_REQUEST_SIZE = 300_000
APP_ID = "obs-nowplaying"
DEFAULT_PORT = 8000
HEARTBEAT_MAX_AGE = 3.0
JSON_FILE = DATA_DIR / "nowplaying.json"
HEARTBEAT_FILE = DATA_DIR / "heartbeat.json"
COVER_FILE = DATA_DIR / "cover.jpg"

PORT = DEFAULT_PORT
RESTART_CALLBACK: Callable[[], None] | None = None
QUIT_CALLBACK: Callable[[], None] | None = None
UPDATE_CALLBACK: Callable[[], None] | None = None
_UPDATE_CACHE: tuple[float, dict[str, Any]] | None = None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _set_start_with_windows(enabled: bool) -> str | None:
    if os.name != "nt":
        return "Start with Windows is only available on Windows."
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}" --no-browser'
                else:
                    command = f'"{sys.executable}" "{RESOURCE_DIR / "app.py"}" --no-browser'
                winreg.SetValueEx(key, "NowPlayingOBS", 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, "NowPlayingOBS")
                except FileNotFoundError:
                    pass
        return None
    except Exception as exc:
        return str(exc)


class OverlayHandler(http.server.SimpleHTTPRequestHandler):
    """Serve embedded UI files and mutable per-user overlay data."""

    server_version = "NowPlaying/2"

    @property
    def request_origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        return not origin or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        origin = self.headers.get("Origin", "")
        if self.request_origin_allowed and origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _json_response(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_data_file(self, target: Path, content_type: str | None = None) -> None:
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204 if self.request_origin_allowed else 403)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/status":
            self._handle_status()
        elif path == "/api/settings":
            self._handle_get_settings()
        elif path == "/api/presets":
            self._json_response(200, {"presets": load_presets()})
        elif path == "/api/update":
            self._handle_update_check()
        elif path == "/nowplaying.json":
            self._send_data_file(JSON_FILE, "application/json; charset=utf-8")
        elif path == "/cover.jpg":
            self._send_data_file(COVER_FILE, "image/jpeg")
        elif path == "/favicon.ico":
            self._send_data_file(RESOURCE_DIR / "assets" / "app-icon.ico", "image/x-icon")
        else:
            super().do_GET()

    def do_POST(self) -> None:
        if not self.request_origin_allowed:
            self._json_response(403, {"error": "Origin not allowed"})
            return
        path = urlsplit(self.path).path
        if path in {"/api/settings", "/save-settings"}:
            self._handle_save_settings()
        elif path == "/api/presets":
            self._handle_save_presets()
        elif path == "/api/restart-detector":
            self._handle_restart_detector()
        elif path == "/api/open-data-folder":
            try:
                os.startfile(DATA_DIR)
                self._json_response(200, {"ok": True})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})
        elif path == "/api/quit":
            self._json_response(200, {"ok": True})
            if QUIT_CALLBACK:
                threading.Thread(target=QUIT_CALLBACK, daemon=True).start()
        elif path == "/api/apply-update":
            if not UPDATE_CALLBACK:
                self._json_response(503, {"error": "Updates are unavailable in server-only mode"})
            else:
                self._json_response(202, {"ok": True})
                threading.Thread(target=UPDATE_CALLBACK, daemon=True).start()
        else:
            self._json_response(404, {"error": "Not found"})

    def _request_json(self) -> Any:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_REQUEST_SIZE:
            raise ValueError("Invalid payload size")
        return json.loads(self.rfile.read(length))

    def _handle_get_settings(self) -> None:
        try:
            self._json_response(200, load_settings(create=True))
        except Exception as exc:
            self._json_response(500, {"error": str(exc)})

    def _handle_save_settings(self) -> None:
        try:
            previous = load_settings()
            data = self._request_json()
            if not isinstance(data, dict):
                raise ValueError("Settings must be a JSON object")
            settings = save_settings(SETTINGS_FILE, data)
            warning = None
            if settings["startWithWindows"] != previous["startWithWindows"]:
                warning = _set_start_with_windows(settings["startWithWindows"])
            response: dict[str, Any] = {"ok": True, "settings": settings}
            if warning:
                response["warning"] = warning
            self._json_response(200, response)
        except (json.JSONDecodeError, ValueError) as exc:
            self._json_response(400, {"error": str(exc)})
        except Exception as exc:
            self._json_response(500, {"error": str(exc)})

    def _handle_save_presets(self) -> None:
        try:
            self._json_response(200, {"ok": True, "presets": save_presets(self._request_json())})
        except (json.JSONDecodeError, ValueError) as exc:
            self._json_response(400, {"error": str(exc)})
        except Exception as exc:
            self._json_response(500, {"error": str(exc)})

    def _handle_restart_detector(self) -> None:
        if not RESTART_CALLBACK:
            self._json_response(503, {"error": "Detector restart is unavailable in server-only mode"})
            return
        RESTART_CALLBACK()
        self._json_response(200, {"ok": True})

    def _handle_status(self) -> None:
        result: dict[str, Any] = {
            "appId": APP_ID,
            "server": True,
            "port": PORT,
            "version": __version__,
            "extractor": False,
            "detectorState": "extractor_stopped",
            "detectorMessage": "No detector heartbeat received.",
            "nowplaying": None,
            "hasCover": COVER_FILE.is_file(),
            "hasSettings": SETTINGS_FILE.is_file(),
            "settingsValid": True,
            "dataDirectory": str(DATA_DIR),
            "logDirectory": str(LOG_DIR),
        }
        try:
            heartbeat = _read_json(HEARTBEAT_FILE) if HEARTBEAT_FILE.is_file() else None
            if heartbeat:
                age = max(0.0, time.time() - float(heartbeat.get("ts", 0)))
                state = str(heartbeat.get("state", "detector_error"))
                result["heartbeatAge"] = round(age, 1)
                result["availableSources"] = heartbeat.get("sources", [])
                terminal = {"stopped", "gsm_tc_unavailable", "detector_error"}
                result["extractor"] = state not in terminal and age <= HEARTBEAT_MAX_AGE
                result["detectorState"] = state if age <= HEARTBEAT_MAX_AGE else "extractor_stopped"
                result["detectorMessage"] = heartbeat.get("error", "")
                if age > HEARTBEAT_MAX_AGE:
                    result["detectorMessage"] = f"Last heartbeat was {age:.1f}s ago."
            if JSON_FILE.is_file():
                result["nowplaying"] = _read_json(JSON_FILE)
            try:
                if SETTINGS_FILE.is_file():
                    from settings_schema import migrate_settings

                    migrate_settings(_read_json(SETTINGS_FILE))
            except Exception as exc:
                result["settingsValid"] = False
                result["detectorState"] = "settings_invalid"
                result["detectorMessage"] = str(exc)
            self._json_response(200, result)
        except Exception as exc:
            self._json_response(500, {"error": str(exc), **result})

    def _handle_update_check(self) -> None:
        global _UPDATE_CACHE
        try:
            if _UPDATE_CACHE and time.time() - _UPDATE_CACHE[0] < 300:
                self._json_response(200, _UPDATE_CACHE[1])
                return
            import update

            release = update.fetch_latest_release()
            if not release:
                self._json_response(503, {"error": "Could not reach GitHub", "current": __version__})
                return
            latest = str(release.get("tag_name", "")).lstrip("v")
            payload = {
                "current": __version__,
                "latest": latest,
                "updateAvailable": update.is_newer_version(latest, __version__),
                "releaseUrl": release.get("html_url", ""),
                "releaseNotes": str(release.get("body", ""))[:4000],
                "automaticUpdate": bool(getattr(sys, "frozen", False) and update.find_asset(release, update.EXE_ASSET_NAME)),
            }
            _UPDATE_CACHE = (time.time(), payload)
            self._json_response(200, payload)
        except Exception as exc:
            self._json_response(500, {"error": str(exc), "current": __version__})

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


class OverlayHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(
    port: int = DEFAULT_PORT,
    *,
    restart_callback: Callable[[], None] | None = None,
    quit_callback: Callable[[], None] | None = None,
    update_callback: Callable[[], None] | None = None,
) -> OverlayHTTPServer:
    global PORT, RESTART_CALLBACK, QUIT_CALLBACK, UPDATE_CALLBACK
    if not 1 <= port <= 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port}")
    PORT = port
    RESTART_CALLBACK = restart_callback
    QUIT_CALLBACK = quit_callback
    UPDATE_CALLBACK = update_callback
    handler = partial(OverlayHandler, directory=str(RESOURCE_DIR))
    return OverlayHTTPServer(("127.0.0.1", port), handler)


def main(
    port: int | None = None,
    *,
    ready_event: threading.Event | None = None,
    restart_callback: Callable[[], None] | None = None,
    quit_callback: Callable[[], None] | None = None,
    update_callback: Callable[[], None] | None = None,
) -> None:
    if port is None:
        try:
            port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
        except ValueError as exc:
            raise ValueError(f"Port must be a number, got '{sys.argv[1]}'") from exc
    httpd = create_server(
        port,
        restart_callback=restart_callback,
        quit_callback=quit_callback,
        update_callback=update_callback,
    )
    initialize_settings()
    print(f"HTTP server running on http://127.0.0.1:{port}")
    print(f"  Overlay   http://127.0.0.1:{port}/overlay.html")
    print(f"  Settings  http://127.0.0.1:{port}/settings.html")
    if ready_event:
        ready_event.set()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
