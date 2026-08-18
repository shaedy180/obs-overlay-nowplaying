"""Windows GSMTC media detector for the OBS Now Playing overlay."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from paths import DATA_DIR, ensure_data_dirs
from settings_schema import SETTINGS_FILE, load_settings


JSON_FILE = DATA_DIR / "nowplaying.json"
HEARTBEAT_FILE = DATA_DIR / "heartbeat.json"
COVER_FILE = DATA_DIR / "cover.jpg"
POLL_INTERVAL = 0.5
MAX_COVER_SIZE = 10 * 1024 * 1024

STATUS_MAP = {
    0: "closed",
    1: "opened",
    2: "changing",
    3: "stopped",
    4: "playing",
    5: "paused",
}


def _write_json(path: str | os.PathLike[str], payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    _replace_with_retry(tmp, target)


def _replace_with_retry(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
    for attempt in range(8):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.015 * (attempt + 1))


def _heartbeat(state: str, *, error: str = "", sources: list[str] | None = None) -> None:
    try:
        _write_json(
            HEARTBEAT_FILE,
            {"ts": time.time(), "state": state, "error": error[:500], "sources": sources or []},
        )
    except OSError:
        pass


async def _save_cover(media_props: Any) -> bool:
    """Extract a session thumbnail and save it atomically."""
    try:
        reference = media_props.thumbnail
        if reference is None:
            return False
        stream = await reference.open_read_async()
        size = stream.size
        if not size or size > MAX_COVER_SIZE:
            return False

        from winrt.windows.storage.streams import DataReader

        reader = DataReader(stream)
        await reader.load_async(size)
        try:
            buffer = bytearray(size)
            reader.read_bytes(buffer)
            data = bytes(buffer)
        except TypeError:
            data = bytes(reader.read_bytes(size))
        if len(data) < 64:
            return False

        tmp = COVER_FILE.with_suffix(".jpg.tmp")
        with tmp.open("wb") as handle:
            handle.write(data)
        _replace_with_retry(tmp, COVER_FILE)
        return True
    except Exception as exc:
        print(f"  [cover] {exc}", file=sys.stderr)
        return False


def _resolve_status(playback_info: Any) -> str:
    if playback_info is None:
        return "unknown"
    try:
        raw = playback_info.playback_status
        return STATUS_MAP.get(int(raw), "unknown")
    except (ValueError, TypeError):
        return str(raw).rsplit(".", 1)[-1].lower()


def _friendly_source(raw_source: str) -> str:
    lower = raw_source.lower()
    mappings = (
        ("spotify", "Spotify"),
        ("apple", "Apple Music"),
        ("itunes", "Apple Music"),
        ("cider", "Apple Music"),
        ("chrome", "Chrome"),
        ("firefox", "Firefox"),
        (("msedge", "microsoftedge"), "Edge"),
        ("vlc", "VLC"),
        ("foobar", "foobar2000"),
        ("musicbee", "MusicBee"),
        ("winamp", "Winamp"),
    )
    for needles, label in mappings:
        if isinstance(needles, str):
            needles = (needles,)
        if any(needle in lower for needle in needles):
            return label
    clean = raw_source.rsplit("!", 1)[-1].rsplit("\\", 1)[-1]
    return clean.removesuffix(".exe") or raw_source or "Unknown"


def _source_info(session: Any) -> tuple[str, str]:
    try:
        raw = session.source_app_user_model_id or ""
    except Exception:
        raw = ""
    return raw, _friendly_source(raw)


def _is_ignored(raw: str, friendly: str, ignored: list[str]) -> bool:
    haystacks = {raw.lower(), friendly.lower()}
    return any(str(item).strip().lower() in haystacks for item in ignored)


def _choose_session(
    manager: Any,
    settings: dict[str, Any],
    preferred_source_id: str = "",
    preferred_session: Any = None,
) -> tuple[Any | None, list[str]]:
    """Select a media session according to Auto/Prefer/Specific settings."""
    current = manager.get_current_session()
    try:
        sessions = list(manager.get_sessions())
    except Exception:
        sessions = [current] if current else []
    if current and all(item is not current for item in sessions):
        sessions.insert(0, current)

    candidates: list[dict[str, Any]] = []
    for session in sessions:
        if session is None:
            continue
        raw, friendly = _source_info(session)
        try:
            status = _resolve_status(session.get_playback_info())
        except Exception:
            status = "unknown"
        candidates.append(
            {
                "session": session,
                "raw": raw,
                "friendly": friendly,
                "status": status,
                "current": session is current,
            }
        )

    available = sorted({item["friendly"] for item in candidates}, key=str.casefold)
    ignored = settings.get("ignoredSources", [])
    usable = [item for item in candidates if not _is_ignored(item["raw"], item["friendly"], ignored)]
    usable.sort(
        key=lambda item: (
            item["status"] == "playing",
            item["session"] is preferred_session,
            bool(preferred_source_id and item["raw"] == preferred_source_id),
            item["current"],
            item["status"] == "paused",
        ),
        reverse=True,
    )

    mode = settings.get("mediaSourceMode", "auto")
    if mode == "specific":
        selected = settings.get("selectedMediaSource", "").strip().lower()
        match = next(
            (
                item for item in usable
                if selected and selected in {item["friendly"].lower(), item["raw"].lower()}
            ),
            None,
        )
        return (match["session"] if match else None), available
    if mode == "preferSpotify":
        spotify = next((item for item in usable if item["friendly"] == "Spotify"), None)
        if spotify:
            return spotify["session"], available
    return (usable[0]["session"] if usable else None), available


def _seconds(value: Any) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "total_seconds"):
        return max(0.0, float(value.total_seconds()))
    if hasattr(value, "duration"):
        return max(0.0, float(value.duration) / 10_000_000)
    try:
        numeric = float(value)
        return max(0.0, numeric / 10_000_000 if numeric > 1_000_000 else numeric)
    except (TypeError, ValueError):
        return 0.0


def _timeline(session: Any) -> tuple[float, float]:
    try:
        timeline = session.get_timeline_properties()
        start = _seconds(getattr(timeline, "start_time", None))
        end = _seconds(getattr(timeline, "end_time", None))
        position = _seconds(getattr(timeline, "position", None))
        duration = max(0.0, end - start) if end > start else end
        if duration and position > duration and start:
            position = max(0.0, position - start)
        return round(min(position, duration) if duration else position, 2), round(duration, 2)
    except Exception:
        return 0.0, 0.0


def _stopping(stop_event: Any) -> bool:
    return bool(stop_event and stop_event.is_set())


async def main(stop_event: Any = None, restart_event: Any = None) -> None:
    ensure_data_dirs()
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as GSMTC,
        )
    except ImportError:
        message = "winrt packages not installed"
        _heartbeat("gsm_tc_unavailable", error=message)
        raise ImportError("winrt packages not installed. Run: pip install -r requirements.txt")

    print("Now Playing detector started.")
    last_cover_key: str | None = None
    last_console_line: str | None = None
    selected_source_id = ""
    selected_session: Any = None

    while not _stopping(stop_event):
        try:
            manager = await GSMTC.request_async()
        except Exception as exc:
            _heartbeat("gsm_tc_unavailable", error=str(exc))
            await asyncio.sleep(3)
            continue

        while not _stopping(stop_event):
            if restart_event and restart_event.is_set():
                restart_event.clear()
                _heartbeat("restarting")
                break

            settings = load_settings(SETTINGS_FILE)
            payload: dict[str, Any] = {
                "title": "",
                "artist": "",
                "album": "",
                "status": "none",
                "source": "",
                "sourceId": "",
                "availableSources": [],
                "hasCover": False,
                "position": 0,
                "duration": 0,
                "timelineTs": time.time(),
                "ts": time.time(),
            }

            try:
                session, available = _choose_session(manager, settings, selected_source_id, selected_session)
                payload["availableSources"] = available
                if session:
                    props = await session.try_get_media_properties_async()
                    playback_info = session.get_playback_info()
                    raw_source, source = _source_info(session)
                    selected_source_id = raw_source
                    selected_session = session
                    title = props.title or ""
                    artist = props.artist or ""
                    album = props.album_title or ""
                    status = _resolve_status(playback_info)
                    position, duration = _timeline(session)

                    cover_key = f"{raw_source}|{title}|{artist}|{album}"
                    if cover_key != last_cover_key:
                        has_cover = await _save_cover(props)
                        last_cover_key = cover_key
                    else:
                        has_cover = COVER_FILE.is_file()

                    payload.update(
                        {
                            "title": title,
                            "artist": artist,
                            "album": album,
                            "status": status,
                            "source": source,
                            "sourceId": raw_source,
                            "hasCover": has_cover,
                            "position": position,
                            "duration": duration,
                            "timelineTs": time.time(),
                            "ts": time.time(),
                        }
                    )

                _write_json(JSON_FILE, payload)
                detector_state = "connected" if session else "no_media_session"
                source_error = ""
                if settings.get("mediaSourceMode") == "specific" and not session:
                    selected = settings.get("selectedMediaSource", "").strip()
                    source_error = f"Selected media source is unavailable: {selected or 'none'}"
                    detector_state = "source_unavailable"
                _heartbeat(detector_state, error=source_error, sources=available)

                console_line = f"{payload['status']}|{payload['title']}|{payload['artist']}|{payload['source']}"
                if console_line != last_console_line:
                    if payload["title"]:
                        print(
                            f"  {payload['status']}: {payload['title']} - "
                            f"{payload['artist']} [{payload['source']}]"
                        )
                    else:
                        print("  no media session")
                    last_console_line = console_line
            except Exception as exc:
                _heartbeat("detector_error", error=str(exc))
                print(f"  [poll] {exc}", file=sys.stderr)

            await asyncio.sleep(POLL_INTERVAL)

    _heartbeat("stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
