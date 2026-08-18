"""Combined background application used by source and one-file builds."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from paths import CACHE_DIR, LOG_DIR, RESOURCE_DIR, ensure_data_dirs


PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}"
OVERLAY_URL = f"{BASE_URL}/overlay.html"
SETTINGS_URL = f"{BASE_URL}/settings.html"
PREVIEW_URL = f"{BASE_URL}/overlay.html?debug&demo"


def _configure_frozen_log() -> None:
    if not getattr(sys, "frozen", False) or sys.stdout is not None:
        return
    ensure_data_dirs()
    stream = (LOG_DIR / "nowplaying.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream


def _message(title: str, message: str, *, error: bool = False) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        (messagebox.showerror if error else messagebox.showinfo)(title, message, parent=root)
        root.destroy()
    except Exception:
        print(f"[{title}] {message}", file=sys.stderr)


def _get_existing_status(timeout: float = 0.7) -> dict | None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if data.get("appId") == "obs-nowplaying" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _port_is_in_use() -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex(("127.0.0.1", PORT)) == 0


def _wait_until_ready(timeout: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _get_existing_status(timeout=0.4):
            return True
        time.sleep(0.15)
    return False


def _copy_to_clipboard(text: str) -> None:
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception as exc:
        print(f"[clipboard] {exc}", file=sys.stderr)


def _create_tray(stop_event: threading.Event, restart_event: threading.Event):
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None

    image = Image.open(RESOURCE_DIR / "assets" / "app-icon.png").convert("RGBA")
    icon = pystray.Icon("NowPlayingOBS", image, "Now Playing for OBS")

    def open_url(url: str):
        return lambda _icon=None, _item=None: webbrowser.open(url)

    def quit_app(tray_icon=None, _item=None):
        stop_event.set()
        if tray_icon:
            tray_icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("Open Settings", open_url(SETTINGS_URL), default=True),
        pystray.MenuItem("Copy OBS URL", lambda *_: _copy_to_clipboard(OVERLAY_URL)),
        pystray.MenuItem("Show Preview", open_url(PREVIEW_URL)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Restart media detection", lambda *_: restart_event.set()),
        pystray.MenuItem("Check for updates", open_url(SETTINGS_URL + "#updates")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )
    return icon


def _start_update_worker(pid: int, original: str) -> None:
    ensure_data_dirs()
    worker = CACHE_DIR / "NowPlaying-update-worker.exe"
    shutil.copy2(original, worker)
    subprocess.Popen(
        [str(worker), "--update-worker", str(pid), original],
        cwd=str(CACHE_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> None:
    ensure_data_dirs()
    _configure_frozen_log()

    if "--update-worker" in sys.argv:
        import update

        update.worker_main(sys.argv)
        return

    if "--update" in sys.argv:
        if getattr(sys, "frozen", False):
            _start_update_worker(os.getpid(), os.path.abspath(sys.executable))
        else:
            webbrowser.open("https://github.com/shaedy180/obs-overlay-nowplaying/releases/latest")
        return

    if _get_existing_status():
        webbrowser.open(SETTINGS_URL)
        return
    if _port_is_in_use():
        _message(
            "Now Playing cannot start",
            "Port 8000 is already used by another application. Close that application and start NowPlaying.exe again.",
            error=True,
        )
        return

    from settings_schema import initialize_settings

    import nowplaying
    import server

    settings, migrated = initialize_settings()
    if migrated:
        print("[settings] Imported legacy settings into the user data directory.")
    if settings.get("startWithWindows"):
        startup_warning = server._set_start_with_windows(True)
        if startup_warning:
            print(f"[startup] Could not synchronize Start with Windows: {startup_warning}", file=sys.stderr)

    stop_event = threading.Event()
    restart_event = threading.Event()
    ready_event = threading.Event()
    startup_error: list[Exception] = []
    tray_holder: dict[str, object] = {}

    def request_quit() -> None:
        stop_event.set()
        tray = tray_holder.get("tray")
        if tray:
            tray.stop()

    def request_update() -> None:
        if not getattr(sys, "frozen", False):
            webbrowser.open("https://github.com/shaedy180/obs-overlay-nowplaying/releases/latest")
            return
        try:
            _start_update_worker(os.getpid(), os.path.abspath(sys.executable))
            time.sleep(0.2)
            request_quit()
        except Exception as exc:
            print(f"[update] {exc}", file=sys.stderr)

    def run_server() -> None:
        try:
            server.main(
                PORT,
                ready_event=ready_event,
                restart_callback=restart_event.set,
                quit_callback=request_quit,
                update_callback=request_update,
            )
        except OSError as exc:
            startup_error.append(exc)
            print(f"[server] {exc}", file=sys.stderr)
            stop_event.set()

    def run_detector() -> None:
        try:
            asyncio.run(nowplaying.main(stop_event, restart_event))
        except Exception as exc:
            print(f"[detector] {exc}", file=sys.stderr)

    threading.Thread(target=run_server, name="http-server", daemon=True).start()
    threading.Thread(target=run_detector, name="media-detector", daemon=True).start()

    if not ready_event.wait(5) or not _wait_until_ready():
        stop_event.set()
        detail = str(startup_error[0]) if startup_error else "The local server did not become healthy."
        _message("Now Playing cannot start", f"The local server on port 8000 could not start.\n\n{detail}", error=True)
        return

    if "--no-browser" not in sys.argv and (
        settings.get("openSettingsOnLaunch", True) or not settings.get("setupComplete", False)
    ):
        webbrowser.open(SETTINGS_URL)

    tray = _create_tray(stop_event, restart_event)
    tray_holder["tray"] = tray
    try:
        if tray:
            tray.run()
        else:
            while not stop_event.wait(0.5):
                pass
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
