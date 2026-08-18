"""Safe updater for the single-file Windows release."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from paths import CACHE_DIR, ensure_data_dirs
from version import __version__


REPO = "shaedy180/obs-overlay-nowplaying"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
EXE_ASSET_NAME = "NowPlaying.exe"
SHA_ASSET_NAME = "NowPlaying.exe.sha256"
MAX_DOWNLOAD_SIZE = 500 * 1024 * 1024
_SEMVER_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")


def get_local_version() -> str:
    return __version__


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.fullmatch(str(value).strip())
    return tuple(int(match.group(index)) for index in range(1, 4)) if match else None


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    candidate_parts = version_tuple(candidate)
    current_parts = version_tuple(current)
    return bool(candidate_parts and current_parts and candidate_parts > current_parts)


def fetch_latest_release() -> dict[str, Any] | None:
    request = urllib.request.Request(API_URL)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "NowPlaying-Updater")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception as exc:
        print(f"Could not reach GitHub: {exc}")
        return None


def find_asset(release: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((asset for asset in release.get("assets", []) if asset.get("name") == name), None)


def _is_safe_path(base_dir: str | os.PathLike[str], relative_path: str | os.PathLike[str]) -> bool:
    """Keep the legacy safety helper for callers that validate relative paths."""
    base = Path(base_dir).resolve()
    target = (base / relative_path).resolve()
    return target == base or base in target.parents


def download_asset(url: str, destination: str | os.PathLike[str], max_size: int = MAX_DOWNLOAD_SIZE) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "NowPlaying-Updater"})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("Download exceeds size limit")
                output.write(chunk)
        os.replace(temporary, target)
        return target
    finally:
        if temporary.exists():
            temporary.unlink()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksum(text: str, filename: str = EXE_ASSET_NAME) -> str:
    for line in text.splitlines():
        parts = line.strip().replace("*", " ").split()
        if parts and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            if len(parts) == 1 or parts[-1] == filename:
                return parts[0].lower()
    raise ValueError("Release checksum is invalid")


def prepare_update(release: dict[str, Any]) -> Path:
    executable_asset = find_asset(release, EXE_ASSET_NAME)
    checksum_asset = find_asset(release, SHA_ASSET_NAME)
    if not executable_asset or not checksum_asset:
        raise ValueError("Release does not contain the required EXE and checksum assets")
    exe_url = executable_asset.get("browser_download_url")
    sha_url = checksum_asset.get("browser_download_url")
    if not exe_url or not sha_url:
        raise ValueError("Release asset URL is missing")

    ensure_data_dirs()
    downloaded = download_asset(exe_url, CACHE_DIR / "NowPlaying.exe.download")
    checksum_path = CACHE_DIR / "NowPlaying.exe.sha256.download"
    try:
        download_asset(sha_url, checksum_path, max_size=64 * 1024)
        expected = parse_checksum(checksum_path.read_text(encoding="utf-8-sig"))
        actual = sha256_file(downloaded)
        if actual != expected:
            raise ValueError("Downloaded EXE failed SHA-256 verification")
        with downloaded.open("rb") as executable:
            header = executable.read(2)
        if downloaded.stat().st_size < 1024 or header != b"MZ":
            raise ValueError("Downloaded file is not a valid Windows executable")
    except Exception:
        downloaded.unlink(missing_ok=True)
        raise
    finally:
        checksum_path.unlink(missing_ok=True)
    return downloaded


def safe_replace_executable(
    downloaded: str | os.PathLike[str],
    original: str | os.PathLike[str],
    backup: str | os.PathLike[str],
) -> None:
    source = Path(downloaded)
    target = Path(original)
    saved = Path(backup)
    saved.unlink(missing_ok=True)
    os.replace(target, saved)
    try:
        os.replace(source, target)
    except Exception:
        os.replace(saved, target)
        raise


def _wait_for_pid(pid: int, timeout: float = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.25)
    return False


def _wait_for_health(process: subprocess.Popen[Any], timeout: float = 20) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=0.5) as response:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("appId") == "obs-nowplaying":
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def perform_update(original: str | os.PathLike[str], check_only: bool = False) -> bool:
    release = fetch_latest_release()
    if not release:
        return False
    latest = str(release.get("tag_name", "")).lstrip("v")
    if not is_newer_version(latest):
        print("Already up to date.")
        return True
    if check_only:
        print(f"Version {latest} is available.")
        return True
    downloaded = prepare_update(release)
    target = Path(original).resolve()
    backup = target.with_suffix(target.suffix + ".backup")
    safe_replace_executable(downloaded, target, backup)
    try:
        process = subprocess.Popen([str(target), "--no-browser"], cwd=str(target.parent))
    except Exception:
        target.unlink(missing_ok=True)
        os.replace(backup, target)
        subprocess.Popen([str(target), "--no-browser"], cwd=str(target.parent))
        raise
    if _wait_for_health(process):
        try:
            backup.unlink(missing_ok=True)
        except OSError:
            pass
        return True

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    target.unlink(missing_ok=True)
    os.replace(backup, target)
    subprocess.Popen([str(target)], cwd=str(target.parent))
    raise RuntimeError("The updated application did not become healthy. The previous version was restored.")


def _schedule_worker_cleanup() -> None:
    worker = Path(sys.executable).resolve()
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "Start-Sleep -Seconds 3; Remove-Item -LiteralPath $args[0] -Force",
                str(worker),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        pass


def worker_main(argv: list[str]) -> None:
    original: Path | None = None
    try:
        marker = argv.index("--update-worker")
        pid = int(argv[marker + 1])
        original = Path(argv[marker + 2]).resolve()
        if original.name.lower() != EXE_ASSET_NAME.lower() or not original.is_file():
            raise ValueError("Invalid application path")
        if not _wait_for_pid(pid):
            raise TimeoutError("The running application did not close")
        perform_update(original)
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        if original and original.is_file():
            time.sleep(1)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=1):
                    pass
            except Exception:
                try:
                    subprocess.Popen([str(original), "--no-browser"], cwd=str(original.parent))
                except OSError:
                    pass
    finally:
        _schedule_worker_cleanup()


def main() -> None:
    if not getattr(sys, "frozen", False):
        print("Automatic replacement is only available in the packaged application.")
        return
    perform_update(sys.executable, check_only="--check" in sys.argv)


if __name__ == "__main__":
    main()
