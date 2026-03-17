"""
Build script - packages everything into a single .exe with PyInstaller.

Usage:
    python build.py

Output:
    dist/NowPlaying/  - folder with NowPlaying.exe and all needed files
    dist/NowPlaying.zip - ready-to-distribute archive
"""

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

# Files to bundle alongside the .exe
DATA_FILES = [
    "overlay.html",
    "settings.html",
    "status.html",
    "version.txt",
    "requirements.txt",
    "LICENSE",
]

# Default settings to include if no settings.json exists yet
INCLUDE_SETTINGS = False


def check_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_exe():
    print("Building NowPlaying.exe ...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", "NowPlaying",
        "--console",
        "--icon", "NONE",
        # Collect the winrt subpackages PyInstaller misses
        "--collect-all", "winrt",
        "--hidden-import", "winrt.windows.media.control",
        "--hidden-import", "winrt.windows.storage.streams",
        "--hidden-import", "winrt.windows.foundation",
        "--hidden-import", "winrt.windows.foundation.collections",
        "app.py",
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def copy_data_files():
    dist_dir = os.path.join(ROOT, "dist", "NowPlaying")
    print(f"Copying data files to {dist_dir} ...")
    for fname in DATA_FILES:
        src = os.path.join(ROOT, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dist_dir)
            print(f"  + {fname}")
        else:
            print(f"  - {fname} (not found, skipping)")

    # Create a simple start.bat for the .exe version
    bat = os.path.join(dist_dir, "start.bat")
    with open(bat, "w") as f:
        f.write('@echo off\r\n')
        f.write('cd /d "%~dp0"\r\n')
        f.write('start "" "http://127.0.0.1:8000/settings.html"\r\n')
        f.write('NowPlaying.exe\r\n')
    print("  + start.bat (generated)")


def make_zip():
    dist_dir = os.path.join(ROOT, "dist", "NowPlaying")
    zip_path = os.path.join(ROOT, "dist", "NowPlaying.zip")
    print(f"Creating {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(dist_dir):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                arcname = os.path.join("NowPlaying", os.path.relpath(full, dist_dir))
                zf.write(full, arcname)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"Done! {size_mb:.1f} MB")


def main():
    check_pyinstaller()
    build_exe()
    copy_data_files()
    make_zip()
    print()
    print("Build complete. Output:")
    print(f"  Folder: dist/NowPlaying/")
    print(f"  ZIP:    dist/NowPlaying.zip")


if __name__ == "__main__":
    main()
