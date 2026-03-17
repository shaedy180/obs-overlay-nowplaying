"""
Self-updater for Now Playing overlay.

Checks the latest GitHub release and downloads + extracts it if a newer
version is available. Preserves settings.json across updates.

Usage:
    python update.py          # check and update
    python update.py --check  # only check, don't download
"""

import json
import os
import shutil
import sys
import urllib.request
import zipfile

REPO = "shaedy180/obs-overlay-nowplaying"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))

VERSION_FILE = os.path.join(ROOT, "version.txt")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
TMP_ZIP = os.path.join(ROOT, ".tmp_download.zip")
MAX_DOWNLOAD_SIZE = 500 * 1024 * 1024  # 500 MB

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


def _is_safe_path(base_dir, rel_path):
    """Ensure rel_path stays within base_dir (no path traversal)."""
    base = os.path.abspath(base_dir)
    target = os.path.abspath(os.path.join(base, rel_path))
    return target.startswith(base + os.sep) or target == base


def download_and_extract(url, target_dir):
    """Download a zip to disk in chunks, then extract it."""
    print("  Downloading ...")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "NowPlaying-Updater")

    # Back up settings before anything else
    settings_backup = None
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings_backup = json.load(f)  # validate it's real JSON
        except Exception as e:
            print(f"  Warning: could not back up settings: {e}")

    try:
        # Stream download to disk instead of loading into RAM
        total = 0
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(TMP_ZIP, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_SIZE:
                        raise ValueError("Download exceeds size limit")
                    f.write(chunk)

        size_mb = total / (1024 * 1024)
        print(f"  Downloaded {size_mb:.1f} MB")

        print("  Extracting ...")
        with zipfile.ZipFile(TMP_ZIP, "r") as zf:
            entries = zf.namelist()
            prefix = ""
            if entries and "/" in entries[0]:
                prefix = entries[0].split("/")[0] + "/"

            for entry in entries:
                if entry.endswith("/"):
                    continue

                rel_path = entry
                if prefix and rel_path.startswith(prefix):
                    rel_path = rel_path[len(prefix):]

                if not rel_path:
                    continue

                if rel_path in KEEP_FILES:
                    continue

                # Path traversal protection
                if not _is_safe_path(target_dir, rel_path):
                    print(f"  Skipping suspicious path: {rel_path}")
                    continue

                dest = os.path.join(target_dir, rel_path)
                dest_dir = os.path.dirname(dest)
                if dest_dir and not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)

                with zf.open(entry) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        print("  Done!")

    finally:
        # Always clean up temp zip
        if os.path.isfile(TMP_ZIP):
            try:
                os.remove(TMP_ZIP)
            except OSError:
                pass

        # Always restore settings from backup
        if settings_backup is not None:
            try:
                tmp = SETTINGS_FILE + ".restore"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(settings_backup, f, indent=2, ensure_ascii=False)
                os.replace(tmp, SETTINGS_FILE)
            except Exception as e:
                print(f"  WARNING: Could not restore settings: {e}")


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
