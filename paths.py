"""Central resource and per-user data paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


APP_DIR_NAME = "NowPlayingOBS"
DATA_ENV_NAME = "NOWPLAYING_DATA_DIR"


def resolve_resource_dir(
    *,
    frozen: bool | None = None,
    meipass: str | os.PathLike[str] | None = None,
    source_file: str | os.PathLike[str] | None = None,
) -> Path:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        location = meipass if meipass is not None else getattr(sys, "_MEIPASS", None)
        if not location:
            raise RuntimeError("Frozen resource directory is unavailable")
        return Path(location).resolve()
    return Path(source_file or __file__).resolve().parent


def resolve_data_dir(
    *,
    environment: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> Path:
    env = os.environ if environment is None else environment
    override = env.get(DATA_ENV_NAME)
    if override:
        return Path(override).expanduser().resolve()

    active_platform = os.name if platform is None else platform
    user_home = Path(home).expanduser() if home is not None else Path.home()
    if active_platform == "nt":
        base = Path(env.get("LOCALAPPDATA") or user_home / "AppData" / "Local")
    else:
        base = Path(env.get("XDG_DATA_HOME") or user_home / ".local" / "share")
    return (base / APP_DIR_NAME).resolve()


def resolve_legacy_dir(*, frozen: bool | None = None, executable: str | None = None) -> Path:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(executable or sys.executable).resolve().parent
    return resolve_resource_dir()


RESOURCE_DIR = resolve_resource_dir()
DATA_DIR = resolve_data_dir()
LEGACY_DIR = resolve_legacy_dir()
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
