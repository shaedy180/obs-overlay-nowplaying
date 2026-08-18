import datetime
import hashlib
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app
import nowplaying
import paths
import presets
import server
import settings_schema
import sizing
import update
from settings_schema import DEFAULTS, VERSION, load_settings, migrate_settings, save_settings


class FakePlaybackInfo:
    def __init__(self, status):
        self.playback_status = status


class FakeSession:
    def __init__(self, source, status):
        self.source_app_user_model_id = source
        self._status = status

    def get_playback_info(self):
        return FakePlaybackInfo(self._status)


class FakeManager:
    def __init__(self, sessions, current):
        self._sessions = sessions
        self._current = current

    def get_sessions(self):
        return self._sessions

    def get_current_session(self):
        return self._current


class SettingsSchemaTests(unittest.TestCase):
    def test_v1_values_are_migrated_and_merged(self):
        result = migrate_settings(
            {
                "overlayWidth": 580,
                "pillBackground": "rgba(12, 24, 36, 0.4)",
                "borderColor": "rgba(200, 210, 220, 0.25)",
                "blurStrength": 40,
                "fontFamily": "Arial, sans-serif",
            }
        )
        self.assertEqual(result["settingsVersion"], VERSION)
        self.assertEqual(result["overlayWidth"], 580)
        self.assertEqual(result["surfaceColor"], "#0c1824")
        self.assertEqual(result["surfaceOpacity"], 0.4)
        self.assertEqual(result["borderColor"], "#c8d2dc")
        self.assertEqual(result["borderOpacity"], 0.25)
        self.assertEqual(result["frosting"], 0.8)
        self.assertEqual(result["fontPreset"], "custom")
        self.assertTrue(result["setupComplete"])

    def test_invalid_values_fall_back_or_clamp(self):
        result = migrate_settings(
            {
                "settingsVersion": 2,
                "overlayWidth": 5000,
                "surfaceColor": "red",
                "progressStyle": "unknown",
                "ignoredSources": "Spotify",
            }
        )
        self.assertEqual(result["overlayWidth"], 900)
        self.assertEqual(result["surfaceColor"], DEFAULTS["surfaceColor"])
        self.assertEqual(result["progressStyle"], DEFAULTS["progressStyle"])
        self.assertEqual(result["ignoredSources"], [])

    def test_invalid_schema_version_is_migrated_safely(self):
        result = migrate_settings({"settingsVersion": "broken", "overlayWidth": 430})
        self.assertEqual(result["settingsVersion"], VERSION)
        self.assertEqual(result["overlayWidth"], 430)

    def test_round_trip_is_atomic_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            saved = save_settings(path, {"settingsVersion": 2, "overlayWidth": 510})
            loaded = load_settings(path)
            self.assertEqual(saved, loaded)
            self.assertEqual(set(loaded), set(DEFAULTS))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["overlayWidth"], 510)

    def test_legacy_file_is_migrated_to_canonical_data_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy"
            legacy.mkdir()
            (legacy / "settings.json").write_text(json.dumps({"overlayWidth": 515}), encoding="utf-8")
            canonical = root / "data" / "settings.json"
            with mock.patch.object(settings_schema, "SETTINGS_FILE", canonical), mock.patch.object(
                settings_schema, "LEGACY_DIR", legacy
            ), mock.patch.object(settings_schema, "ensure_data_dirs"):
                result, migrated = settings_schema.initialize_settings()
            self.assertTrue(migrated)
            self.assertEqual(result["overlayWidth"], 515)
            self.assertEqual(json.loads(canonical.read_text(encoding="utf-8"))["settingsVersion"], VERSION)


class PathTests(unittest.TestCase):
    def test_source_resource_path_uses_module_parent(self):
        target = paths.resolve_resource_dir(source_file=r"C:\repo\project\paths.py", frozen=False)
        self.assertEqual(target, Path(r"C:\repo\project").resolve())

    def test_frozen_resource_path_uses_meipass(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(paths.resolve_resource_dir(frozen=True, meipass=directory), Path(directory).resolve())

    def test_windows_data_path_uses_local_appdata(self):
        with tempfile.TemporaryDirectory() as directory:
            result = paths.resolve_data_dir(environment={"LOCALAPPDATA": directory}, platform="nt")
            self.assertEqual(result, (Path(directory) / "NowPlayingOBS").resolve())


class PresetTests(unittest.TestCase):
    def test_custom_presets_persist_and_strip_app_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "presets.json"
            saved = presets.save_presets(
                {"presets": [{"id": "night-1", "name": "Night", "settings": {"overlayWidth": 525, "startWithWindows": True}}]},
                target,
            )
            loaded = presets.load_presets(target)
            self.assertEqual(saved, loaded)
            self.assertEqual(loaded[0]["settings"]["overlayWidth"], 525)
            self.assertNotIn("startWithWindows", loaded[0]["settings"])

    def test_preset_names_and_count_are_validated(self):
        values = [{"name": f" Preset {index} ", "settings": {}} for index in range(60)]
        result = presets.validate_presets(values)
        self.assertEqual(len(result), presets.MAX_PRESETS)
        self.assertEqual(result[0]["name"], "Preset 0")


class MediaSelectionTests(unittest.TestCase):
    def setUp(self):
        self.chrome = FakeSession("chrome.exe", 4)
        self.spotify = FakeSession("Spotify.exe", 5)
        self.vlc = FakeSession("vlc.exe", 4)
        self.manager = FakeManager([self.chrome, self.spotify, self.vlc], self.chrome)

    def test_auto_prefers_current_playing_session(self):
        session, sources = nowplaying._choose_session(
            self.manager, {"mediaSourceMode": "auto", "ignoredSources": []}
        )
        self.assertIs(session, self.chrome)
        self.assertEqual(sources, ["Chrome", "Spotify", "VLC"])

    def test_spotify_preference_overrides_current_session(self):
        session, _ = nowplaying._choose_session(
            self.manager, {"mediaSourceMode": "preferSpotify", "ignoredSources": []}
        )
        self.assertIs(session, self.spotify)

    def test_specific_and_ignored_sources(self):
        session, _ = nowplaying._choose_session(
            self.manager,
            {
                "mediaSourceMode": "specific",
                "selectedMediaSource": "VLC",
                "ignoredSources": [],
            },
        )
        self.assertIs(session, self.vlc)
        session, _ = nowplaying._choose_session(
            self.manager,
            {
                "mediaSourceMode": "specific",
                "selectedMediaSource": "VLC",
                "ignoredSources": ["VLC"],
            },
        )
        self.assertIsNone(session)

    def test_auto_skips_ignored_current_source(self):
        session, _ = nowplaying._choose_session(
            self.manager,
            {"mediaSourceMode": "auto", "ignoredSources": ["Chrome"]},
        )
        self.assertIs(session, self.vlc)

    def test_auto_prefers_playing_browser_over_paused_spotify(self):
        session, _ = nowplaying._choose_session(
            self.manager, {"mediaSourceMode": "auto", "ignoredSources": []}
        )
        self.assertIs(session, self.chrome)

    def test_equivalent_sessions_keep_previous_session(self):
        other_chrome = FakeSession("chrome.exe", 4)
        manager = FakeManager([other_chrome, self.chrome], other_chrome)
        session, _ = nowplaying._choose_session(
            manager,
            {"mediaSourceMode": "auto", "ignoredSources": []},
            preferred_source_id="chrome.exe",
            preferred_session=self.chrome,
        )
        self.assertIs(session, self.chrome)

    def test_timedelta_conversion(self):
        self.assertEqual(nowplaying._seconds(datetime.timedelta(minutes=1, seconds=2)), 62)

    def test_atomic_replace_retries_windows_file_lock(self):
        with mock.patch.object(nowplaying.os, "replace", side_effect=[PermissionError(), PermissionError(), None]) as replace:
            with mock.patch.object(nowplaying.time, "sleep"):
                nowplaying._replace_with_retry("source.tmp", "destination.json")
        self.assertEqual(replace.call_count, 3)


class LauncherAndUpdaterTests(unittest.TestCase):
    def test_second_launch_opens_settings_without_starting_services(self):
        with mock.patch.object(app, "_get_existing_status", return_value={"appId": "obs-nowplaying"}), mock.patch.object(
            app.webbrowser, "open"
        ) as open_browser:
            app.main()
        open_browser.assert_called_once_with(app.SETTINGS_URL)

    def test_updater_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(update._is_safe_path(directory, "assets/overlay.html"))
            self.assertFalse(update._is_safe_path(directory, "../outside.exe"))

    def test_port_validation_happens_before_binding(self):
        with self.assertRaises(ValueError):
            server.create_server(0)

    def test_port_probe_reports_connect_result(self):
        probe = mock.MagicMock()
        probe.__enter__.return_value = probe
        probe.connect_ex.return_value = 0
        with mock.patch("socket.socket", return_value=probe):
            self.assertTrue(app._port_is_in_use())

    def test_semver_only_reports_newer_versions(self):
        self.assertTrue(update.is_newer_version("2.1.0", "2.0.0"))
        self.assertFalse(update.is_newer_version("2.0.0", "2.0.0"))
        self.assertFalse(update.is_newer_version("1.9.9", "2.0.0"))
        self.assertFalse(update.is_newer_version("latest", "2.0.0"))

    def test_updater_selects_exact_exe_asset(self):
        archive_name = "NowPlaying" + ".zip"
        release = {"assets": [{"name": "Helper.exe"}, {"name": "NowPlaying.exe"}, {"name": archive_name}]}
        self.assertEqual(update.find_asset(release, update.EXE_ASSET_NAME)["name"], "NowPlaying.exe")
        self.assertIsNone(update.find_asset(release, "nowplaying.exe"))

    def test_checksum_parser_requires_matching_asset_name(self):
        digest = "a" * 64
        self.assertEqual(update.parse_checksum(f"{digest}  NowPlaying.exe"), digest)
        with self.assertRaises(ValueError):
            update.parse_checksum(f"{digest}  Helper.exe")

    def test_prepare_update_verifies_checksum_and_cleans_checksum_file(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            executable = b"MZ" + b"x" * 2048
            digest = hashlib.sha256(executable).hexdigest()
            release = {"assets": [
                {"name": update.EXE_ASSET_NAME, "browser_download_url": "exe-url"},
                {"name": update.SHA_ASSET_NAME, "browser_download_url": "sha-url"},
            ]}

            def fake_download(url, destination, max_size=update.MAX_DOWNLOAD_SIZE):
                target = Path(destination)
                target.write_bytes(executable if url == "exe-url" else f"{digest}  NowPlaying.exe\n".encode())
                return target

            with mock.patch.object(update, "CACHE_DIR", cache), mock.patch.object(update, "ensure_data_dirs"), mock.patch.object(
                update, "download_asset", side_effect=fake_download
            ):
                result = update.prepare_update(release)
            self.assertTrue(result.is_file())
            self.assertFalse((cache / "NowPlaying.exe.sha256.download").exists())

    def test_safe_executable_replacement_keeps_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, downloaded, backup = root / "NowPlaying.exe", root / "new.exe", root / "old.backup"
            original.write_bytes(b"old")
            downloaded.write_bytes(b"new")
            update.safe_replace_executable(downloaded, original, backup)
            self.assertEqual(original.read_bytes(), b"new")
            self.assertEqual(backup.read_bytes(), b"old")

    def test_safe_executable_replacement_rolls_back_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, downloaded, backup = root / "NowPlaying.exe", root / "new.exe", root / "old.backup"
            original.write_bytes(b"old")
            downloaded.write_bytes(b"new")
            real_replace = os.replace
            calls = 0

            def fail_second(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError("locked")
                return real_replace(source, destination)

            with mock.patch.object(update.os, "replace", side_effect=fail_second):
                with self.assertRaises(PermissionError):
                    update.safe_replace_executable(downloaded, original, backup)
            self.assertEqual(original.read_bytes(), b"old")

    def test_updater_has_no_archive_dependency(self):
        source = inspect.getsource(update)
        self.assertNotIn("zipfile", source)
        self.assertNotIn("find_" + "zip_asset", source)


class SizingAndBuildTests(unittest.TestCase):
    def test_default_obs_size_matches_documented_geometry(self):
        self.assertEqual(sizing.required_obs_size(DEFAULTS), (472, 122))

    def test_hidden_cover_uses_text_height(self):
        width, height = sizing.required_obs_size({**DEFAULTS, "showAlbumArt": False, "showEqualizer": False})
        self.assertEqual(width, 472)
        self.assertLess(height, 122)

    def test_frontends_use_schema_layout_metrics(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("settings.html", "overlay.html"):
            source = (root / name).read_text(encoding="utf-8")
            self.assertIn("layoutMetrics.outerMargin", source)
            self.assertIn("layoutMetrics.overlayVerticalPadding", source)

    def test_build_is_windowed_onefile_and_workflow_publishes_exe(self):
        root = Path(__file__).resolve().parents[1]
        build_source = (root / "build.py").read_text(encoding="utf-8")
        workflow = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn('"--onefile"', build_source)
        self.assertIn('"--windowed"', build_source)
        self.assertIn("dist/NowPlaying.exe", workflow)
        self.assertIn("dist/NowPlaying.exe.sha256", workflow)
        self.assertNotIn("NowPlaying" + ".zip", workflow)


if __name__ == "__main__":
    unittest.main()
