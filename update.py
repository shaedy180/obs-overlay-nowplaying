"""
Self-updater for Now Playing overlay.

Checks the latest GitHub release and downloads + extracts it if a newer
version is available. Preserves settings.json across updates.

Usage:
    python update.py          # check and update
    python update.py --check  # only check, don't download
"""

import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

REPO = "shaedy180/obs-overlay-nowplaying"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ROOT = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(ROOT, "version.txt")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")

# Files that should never be overwritten by an update
KEEP_FILES = {"settings.json", "nowplaying.json", "cover.jpg"}


def get_local_version():
    if os.path.isfile(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return "0.0.0"


def fetch_latest_release():
    """Ask the GitHub API for the latest release info."""
    req = urllib.request.Request(API_URL)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "NowPlaying-Updater")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  Could not reach GitHub: {e}")
        return None


def find_zip_asset(release):
    """Find the NowPlaying.zip asset in a release."""
    for asset in release.get("assets", []):
        if asset["name"].lower().endswith(".zip"):
            return asset
    return None


def download_and_extract(url, target_dir):
    """Download a zip from url and extract it to target_dir."""
    print(f"  Downloading ...")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "NowPlaying-Updater")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    size_mb = len(data) / (1024 * 1024)
    print(f"  Downloaded {size_mb:.1f} MB")

    # Back up settings before extracting
    settings_backup = None
    if os.path.isfile(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings_backup = f.read()

    print("  Extracting ...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # The zip typically contains a top-level folder like NowPlaying/
        # We need to strip that prefix and extract into target_dir
        entries = zf.namelist()
        prefix = ""
        if entries and "/" in entries[0]:
            prefix = entries[0].split("/")[0] + "/"

        for entry in entries:
            # Skip directories
            if entry.endswith("/"):
                continue

            # Strip the prefix folder
            rel_path = entry
            if prefix and rel_path.startswith(prefix):
                rel_path = rel_path[len(prefix):]

            if not rel_path:
                continue

            # Don't overwrite user files
            if rel_path in KEEP_FILES:
                continue

            dest = os.path.join(target_dir, rel_path)
            dest_dir = os.path.dirname(dest)
            if dest_dir and not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            with zf.open(entry) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    # Restore settings if they existed
    if settings_backup is not None:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write(settings_backup)

    print("  Done!")


def main():
    check_only = "--check" in sys.argv

    local_ver = get_local_version()
    print(f"  Current version: {local_ver}")

    release = fetch_latest_release()
    if not release:
        return

    tag = release.get("tag_name", "").lstrip("v")
    print(f"  Latest release:  {tag}")

    if tag == local_ver:
        print("  Already up to date.")
        return

    if not tag:
        print("  Could not determine latest version.")
        return

    asset = find_zip_asset(release)
    if not asset:
        print("  No .zip asset found in the latest release.")
        print(f"  Check manually: https://github.com/{REPO}/releases/latest")
        return

    print(f"  New version available: {tag}")

    if check_only:
        print(f"  Run without --check to update.")
        return

    download_url = asset.get("browser_download_url")
    if not download_url:
        print("  Could not find download URL.")
        return

    download_and_extract(download_url, ROOT)
    print(f"  Updated to version {tag}!")
    print("  Restart the application to use the new version.")


if __name__ == "__main__":
    main()
