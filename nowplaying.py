"""
Now Playing extractor - reads Windows media controls (GSMTC)
and writes nowplaying.json + cover.jpg for the OBS overlay.

Works with Spotify, Apple Music, browsers, and anything that
shows up in the Windows volume flyout.
"""

import asyncio
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(SCRIPT_DIR, "nowplaying.json")
COVER_FILE = os.path.join(SCRIPT_DIR, "cover.jpg")
POLL_INTERVAL = 0.5

# Playback status enum values from Windows.Media.Control
STATUS_MAP = {
    0: "closed",
    1: "opened",
    2: "changing",
    3: "stopped",
    4: "playing",
    5: "paused",
}


def _write_json(payload: dict) -> None:
    """Write JSON atomically (temp file, then rename)."""
    tmp = JSON_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, JSON_FILE)


async def _save_cover(media_props) -> bool:
    """Extract album-art thumbnail from the media session and save as cover.jpg."""
    try:
        ref = media_props.thumbnail
        if ref is None:
            return False

        stream = await ref.open_read_async()
        size = stream.size
        if not size or size == 0:
            return False

        from winrt.windows.storage.streams import DataReader

        reader = DataReader(stream)
        await reader.load_async(size)

        # Handle different winrt binding versions
        try:
            buf = bytearray(size)
            reader.read_bytes(buf)
            data = bytes(buf)
        except TypeError:
            data = bytes(reader.read_bytes(size))

        if len(data) < 64:
            return False

        with open(COVER_FILE, "wb") as f:
            f.write(data)
        return True

    except Exception as exc:
        print(f"  [cover] {exc}", file=sys.stderr)
        return False


def _resolve_status(playback_info) -> str:
    """Convert the playback-status enum to a clean string."""
    if playback_info is None:
        return "unknown"
    try:
        raw = playback_info.playback_status
        return STATUS_MAP.get(int(raw), "unknown")
    except (ValueError, TypeError):
        return str(raw).rsplit(".", 1)[-1].lower()


async def main() -> None:
    # Import winrt (split packages)
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as GSMTC,
        )
    except ImportError:
        print(
            "ERROR: winrt packages not installed.\n"
            "Run:  pip install winrt-runtime "
            "winrt-Windows.Media.Control winrt-Windows.Storage.Streams"
        )
        sys.exit(1)

    print("Now Playing extractor started.")
    print(f"  JSON  -> {JSON_FILE}")
    print(f"  Cover -> {COVER_FILE}")
    print(f"  Polling every {POLL_INTERVAL:.1f}s -- Ctrl+C to stop.\n")

    mgr = await GSMTC.request_async()

    last_json = None
    last_cover_key = None

    while True:
        payload = {
            "title": "",
            "artist": "",
            "album": "",
            "status": "none",
            "source": "",
            "hasCover": False,
            "ts": time.time(),
        }

        try:
            session = mgr.get_current_session()
            if session:
                props = await session.try_get_media_properties_async()
                info = session.get_playback_info()

                title = props.title or ""
                artist = props.artist or ""
                album = props.album_title or ""
                status = _resolve_status(info)

                # Try to get the source app name
                source = ""
                try:
                    source = session.source_app_user_model_id or ""
                    # Clean up common app IDs to friendly names
                    source_lower = source.lower()
                    if "spotify" in source_lower:
                        source = "Spotify"
                    elif "apple" in source_lower or "itunes" in source_lower or "cider" in source_lower:
                        source = "Apple Music"
                    elif "chrome" in source_lower:
                        source = "Chrome"
                    elif "firefox" in source_lower:
                        source = "Firefox"
                    elif "edge" in source_lower:
                        source = "Edge"
                    elif "vlc" in source_lower:
                        source = "VLC"
                    elif "foobar" in source_lower:
                        source = "foobar2000"
                    elif "musicbee" in source_lower:
                        source = "MusicBee"
                    elif "winamp" in source_lower:
                        source = "Winamp"
                except Exception:
                    pass

                # Save cover art only when track changes
                cover_key = f"{title}|{artist}|{album}"
                if cover_key != last_cover_key:
                    has_cover = await _save_cover(props)
                    last_cover_key = cover_key
                else:
                    has_cover = os.path.isfile(COVER_FILE)

                payload.update(
                    {
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "status": status,
                        "source": source,
                        "hasCover": has_cover,
                        "ts": time.time(),
                    }
                )

        except Exception as exc:
            print(f"  [poll] {exc}", file=sys.stderr)

        # Only write when something meaningful changed
        check = {k: v for k, v in payload.items() if k != "ts"}
        check_str = json.dumps(check, ensure_ascii=False)
        if check_str != last_json:
            payload["ts"] = time.time()
            _write_json(payload)
            last_json = check_str

            icon = {"playing": ">", "paused": "|", "none": "."}.get(payload["status"], "?")
            if payload["title"]:
                print(f"  {icon}  {payload['title']} - {payload['artist']}")
            else:
                print(f"  {icon}  (nothing playing)")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
