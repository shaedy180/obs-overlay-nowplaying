"""Shared settings loading, validation and legacy migration."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from paths import DATA_DIR, LEGACY_DIR, RESOURCE_DIR, ensure_data_dirs

SCHEMA_FILE = RESOURCE_DIR / "settings.schema.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

with SCHEMA_FILE.open("r", encoding="utf-8") as _schema_handle:
    SCHEMA = json.load(_schema_handle)

VERSION: int = SCHEMA["version"]
DEFAULTS: dict[str, Any] = SCHEMA["defaults"]
LIMITS: dict[str, list[float]] = SCHEMA.get("limits", {})

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})"
    r"(?:\s*,\s*(0|1|0?\.\d+))?\s*\)",
    re.IGNORECASE,
)


def _rgba_parts(value: Any, fallback_color: str, fallback_alpha: float) -> tuple[str, float]:
    if not isinstance(value, str):
        return fallback_color, fallback_alpha
    value = value.strip()
    if _HEX_RE.fullmatch(value):
        return value.lower(), fallback_alpha
    match = _RGBA_RE.fullmatch(value)
    if not match:
        return fallback_color, fallback_alpha
    red, green, blue = (max(0, min(255, int(match.group(i)))) for i in range(1, 4))
    alpha = float(match.group(4)) if match.group(4) is not None else 1.0
    return f"#{red:02x}{green:02x}{blue:02x}", max(0.0, min(1.0, alpha))


def migrate_settings(raw: Any, *, existing_file: bool = True) -> dict[str, Any]:
    """Return a complete, validated settings object.

    Unknown keys are intentionally dropped so imported/custom JSON cannot grow
    without bounds. Existing v1 installs skip the first-run wizard.
    """
    source = raw if isinstance(raw, dict) else {}
    migrated = dict(source)
    try:
        old_version = int(source.get("settingsVersion", 1) or 1)
    except (TypeError, ValueError):
        old_version = 1

    if old_version < 2:
        try:
            old_blur = float(source.get("blurStrength", 28))
        except (TypeError, ValueError):
            old_blur = 28
        surface, surface_alpha = _rgba_parts(
            source.get("pillBackground"),
            DEFAULTS["surfaceColor"],
            DEFAULTS["surfaceOpacity"],
        )
        border, border_alpha = _rgba_parts(
            source.get("borderColor"),
            DEFAULTS["borderColor"],
            DEFAULTS["borderOpacity"],
        )
        migrated.update(
            {
                "surfaceColor": surface,
                "surfaceOpacity": surface_alpha,
                "borderColor": border,
                "borderOpacity": border_alpha,
                "frosting": max(0.0, min(1.0, old_blur / 50)),
                "setupComplete": existing_file,
            }
        )
        old_font = source.get("fontFamily")
        if isinstance(old_font, str) and old_font.strip():
            migrated["customFontFamily"] = old_font.strip()
            if "segoe" not in old_font.lower():
                migrated["fontPreset"] = "custom"

    result: dict[str, Any] = {}
    for key, default in DEFAULTS.items():
        value = migrated.get(key, default)
        if isinstance(default, bool):
            value = value if isinstance(value, bool) else default
        elif isinstance(default, (int, float)) and not isinstance(default, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                value = default
            if key in LIMITS:
                minimum, maximum = LIMITS[key]
                value = max(minimum, min(maximum, value))
            if isinstance(default, int):
                value = int(value)
            else:
                value = float(value)
        elif isinstance(default, list):
            if not isinstance(value, list):
                value = list(default)
            else:
                value = [str(item).strip() for item in value if str(item).strip()][:50]
        elif isinstance(default, str):
            value = str(value)[:10_000] if value is not None else default
        result[key] = value

    for color_key in ("surfaceColor", "borderColor", "textColor", "accentColorFixed"):
        if not _HEX_RE.fullmatch(str(result[color_key])):
            result[color_key] = DEFAULTS[color_key]

    allowed_values = {
        "sizeMode": {"fixed", "fit"},
        "accentColorMode": {"auto", "fixed"},
        "fontPreset": {"segoe", "inter", "arial", "georgia", "mono", "custom"},
        "animationStyle": {"smooth", "slide", "minimal", "none"},
        "progressStyle": {"off", "accent", "minimal", "time"},
        "mediaSourceMode": {"auto", "preferSpotify", "specific"},
    }
    for key, allowed in allowed_values.items():
        if result[key] not in allowed:
            result[key] = DEFAULTS[key]

    result["settingsVersion"] = VERSION
    return result


def load_settings(path: str | os.PathLike[str] = SETTINGS_FILE, *, create: bool = False) -> dict[str, Any]:
    target = Path(path)
    exists = target.is_file()
    raw: Any = {}
    if exists:
        try:
            with target.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            raw = {}
    settings = migrate_settings(raw, existing_file=exists)
    if create and (not exists or settings != raw):
        save_settings(target, settings)
    return settings


def save_settings(path: str | os.PathLike[str], raw: Any) -> dict[str, Any]:
    settings = migrate_settings(raw, existing_file=True)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2, ensure_ascii=False)
    for attempt in range(8):
        try:
            os.replace(tmp, target)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.015 * (attempt + 1))
    return settings


def initialize_settings() -> tuple[dict[str, Any], bool]:
    """Create the canonical settings file and import one legacy file once."""
    ensure_data_dirs()
    if SETTINGS_FILE.is_file():
        return load_settings(SETTINGS_FILE, create=True), False

    legacy_file = LEGACY_DIR / "settings.json"
    if legacy_file.resolve() != SETTINGS_FILE.resolve() and legacy_file.is_file():
        try:
            raw = json.loads(legacy_file.read_text(encoding="utf-8"))
            settings = save_settings(SETTINGS_FILE, raw)
            return settings, True
        except (OSError, json.JSONDecodeError):
            pass

    settings = migrate_settings({}, existing_file=False)
    save_settings(SETTINGS_FILE, settings)
    return settings, False
