"""Build the self-contained Windows executable with PyInstaller."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from version import __version__


ROOT = Path(__file__).resolve().parent
DIST_EXE = ROOT / "dist" / "NowPlaying.exe"
CHECKSUM_FILE = ROOT / "dist" / "NowPlaying.exe.sha256"
RESOURCE_FILES = ["overlay.html", "settings.html", "status.html", "settings.schema.json"]


def check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def _version_parts() -> tuple[int, int, int, int]:
    values = tuple(int(part) for part in __version__.split("."))
    if len(values) != 3:
        raise ValueError("version.py must contain a three-part version")
    return values + (0,)


def write_version_metadata() -> Path:
    parts = _version_parts()
    path = ROOT / "build" / "windows-file-metadata.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    dotted = ", ".join(str(value) for value in parts)
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({dotted}), prodvers=({dotted}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Now Playing for OBS'),
    StringStruct('FileDescription', 'Now Playing overlay service for OBS'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', 'NowPlaying'),
    StringStruct('OriginalFilename', 'NowPlaying.exe'),
    StringStruct('ProductName', 'Now Playing for OBS'),
    StringStruct('ProductVersion', '{__version__}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)""",
        encoding="utf-8",
    )
    return path


def build_exe() -> Path:
    version_file = write_version_metadata()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "NowPlaying",
        "--onefile",
        "--windowed",
        "--icon",
        str(ROOT / "assets" / "app-icon.ico"),
        "--version-file",
        str(version_file),
        "--collect-all",
        "winrt",
        "--collect-all",
        "pystray",
        "--hidden-import",
        "winrt.windows.media.control",
        "--hidden-import",
        "winrt.windows.storage.streams",
        "--hidden-import",
        "winrt.windows.system",
        "--hidden-import",
        "winrt.windows.foundation",
        "--hidden-import",
        "winrt.windows.foundation.collections",
    ]
    for name in RESOURCE_FILES:
        command.extend(["--add-data", f"{ROOT / name};."])
    command.extend(["--add-data", f"{ROOT / 'assets'};assets", str(ROOT / "app.py")])
    subprocess.check_call(command, cwd=ROOT)
    if not DIST_EXE.is_file() or DIST_EXE.stat().st_size < 1024:
        raise RuntimeError("PyInstaller did not create dist/NowPlaying.exe")
    with DIST_EXE.open("rb") as executable:
        if executable.read(2) != b"MZ":
            raise RuntimeError("Build output is not a Windows executable")
    return DIST_EXE


def write_checksum(path: Path) -> Path:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    CHECKSUM_FILE.write_text(f"{digest.hexdigest()}  {path.name}\n", encoding="ascii")
    return CHECKSUM_FILE


def main() -> None:
    check_pyinstaller()
    executable = build_exe()
    checksum = write_checksum(executable)
    print(f"Built {executable}")
    print(f"Checksum {checksum}")


if __name__ == "__main__":
    main()
