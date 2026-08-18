"""Validated custom preset storage in the per-user data directory."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from paths import DATA_DIR, ensure_data_dirs
from settings_schema import DEFAULTS, migrate_settings


PRESETS_FILE = DATA_DIR / "presets.json"
MAX_PRESETS = 50
MAX_NAME_LENGTH = 48
FORMAT_VERSION = 1
_ID_RE = re.compile(r"^[a-z0-9-]{1,64}$")
_NON_STYLE_KEYS = {
    "settingsVersion",
    "setupComplete",
    "mediaSourceMode",
    "selectedMediaSource",
    "ignoredSources",
    "startWithWindows",
    "openSettingsOnLaunch",
}


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.015 * (attempt + 1))


def style_settings(raw: Any) -> dict[str, Any]:
    settings = migrate_settings(raw)
    return {key: value for key, value in settings.items() if key not in _NON_STYLE_KEYS}


def validate_presets(raw: Any) -> list[dict[str, Any]]:
    source = raw.get("presets", []) if isinstance(raw, dict) else raw
    if not isinstance(source, list):
        raise ValueError("Presets must be a list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in source[:MAX_PRESETS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:MAX_NAME_LENGTH]
        if not name:
            continue
        preset_id = str(item.get("id", "")).lower()
        if not _ID_RE.fullmatch(preset_id) or preset_id in seen:
            preset_id = uuid.uuid4().hex
        seen.add(preset_id)
        result.append({"id": preset_id, "name": name, "settings": style_settings(item.get("settings", {}))})
    return result


def load_presets(path: str | os.PathLike[str] = PRESETS_FILE) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        return []
    try:
        return validate_presets(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def save_presets(raw: Any, path: str | os.PathLike[str] = PRESETS_FILE) -> list[dict[str, Any]]:
    ensure_data_dirs()
    presets = validate_presets(raw)
    _atomic_json(Path(path), {"version": FORMAT_VERSION, "presets": presets})
    return presets
