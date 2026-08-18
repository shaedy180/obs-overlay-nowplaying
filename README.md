# Now Playing for OBS

Now Playing for OBS is a small Windows background app that displays the active media session in an OBS Browser Source. It supports Spotify, Apple Music, browsers, VLC, and other apps that use Windows media controls.

## Quick start

1. Download `NowPlaying.exe` from the [latest release](https://github.com/shaedy180/obs-overlay-nowplaying/releases/latest).
2. Double-click `NowPlaying.exe`. No installation or extraction is required.
3. Complete the first-run setup.
4. Add a Browser Source in OBS.
5. Copy the URL, width, and height shown in the settings dashboard.

The default Browser Source values are:

```text
URL:    http://127.0.0.1:8000/overlay.html
Width:  472
Height: 122
```

The dashboard recalculates the required dimensions when the overlay changes and warns if the preview viewport would clip it.

`NowPlaying.exe` is a self-contained, windowed app. End users do not need Python, a terminal, a batch file, or files next to the EXE.

## App behavior

The app runs in the Windows notification area. Closing the settings browser tab does not stop it. The tray menu provides:

- Open Settings
- Copy OBS URL
- Show Preview
- Restart media detection
- Check for updates
- Quit

Starting the EXE a second time opens the existing settings page without starting another server or media detector. If another application occupies port 8000, a clear Windows error dialog is shown.

## Settings and user data

Persistent data is stored per user at:

```text
%LOCALAPPDATA%\NowPlayingOBS
```

This directory contains settings, custom presets, current media data, cover art, logs, update cache, and diagnostics heartbeat data. App updates never replace these files.

If a previous version has `settings.json` next to the EXE, the first v2 start validates, migrates, and copies it into the new user data directory. Settings schema versions 1 and 2 are migrated to version 3.

## Settings dashboard

Open the dashboard at:

```text
http://127.0.0.1:8000/settings.html
```

It includes a sticky live preview, fixed and fit sizing modes, OBS size calculation, clipping checks, media source selection, immediate rendering, autosave, undo, section reset, diagnostics, import and export, and custom presets stored by the app.

Preview backgrounds include dark, light, colorful, gameplay, and transparency grid. Test states include playing, paused, idle, no cover, long title, and track change. Preview metadata and cover uploads do not alter real media data.

Only Finish setup completes the first-run wizard. Test overlay opens a demonstration and leaves setup active.

## Media selection

Windows may expose multiple media sessions. The detector supports:

- Auto selection with stable preference for the current playing source
- Prefer Spotify, otherwise Auto
- A specific source
- Ignored sources

Playing sessions rank above paused sessions. A previously selected playing source remains stable when equivalent sessions are present. Missing specific sources and ignore conflicts are reported in the UI and diagnostics.

## Overlay features

- Album cover and optional cover-derived primary and secondary accents
- Track progress with accent, minimal, and time modes
- Separate cover and metadata motion for track changes
- Smooth, Slide, Minimal, and None animation modes
- Long-title marquee with pauses at both ends
- Hide or dim on pause and hide on idle
- Reduced-motion support
- Custom CSS in Advanced settings
- Core, Terminal, Signal, Outline, and Compact built-in presets

The default product style is black, gray, and neon green with square geometry and restrained technical motion. Cover colors remain optional and are normalized for usable saturation and luminance.

## Diagnostics

The settings header shows current detector state, source, playback, and version. Detailed diagnostics are available at:

```text
http://127.0.0.1:8000/status.html
```

Heartbeat state distinguishes connected, no media session, missing specific source, stopped detector, unavailable GSMTC, detector errors, and invalid settings. Frozen builds write logs to `%LOCALAPPDATA%\NowPlayingOBS\logs\nowplaying.log`.

## Updates

The Advanced tab checks the latest GitHub release. A newer semantic version can be downloaded as the exact `NowPlaying.exe` asset. The updater verifies `NowPlaying.exe.sha256`, closes the current process, replaces the EXE, restarts it, and restores the previous executable if the new version does not become healthy.

Settings and presets remain untouched because they live in the separate user data directory.

## Development / Running from source

Requirements:

- Windows 10 or 11
- Python 3.10 or newer
- OBS Studio for normal use

From the repository directory:

```bat
start.bat
```

The development launcher creates `venv`, installs dependencies, starts the combined app, and waits for the health endpoint. It is not part of the end-user release.

Manual setup:

```bat
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe app.py
```

For server-only frontend work:

```bat
venv\Scripts\python.exe server.py
```

Server-only mode serves the editor and demo preview but does not start GSMTC detection or the tray app.

## Building the standalone app

```bat
python -m pip install pyinstaller
python -m pip install -r requirements.txt
python build.py
```

The build creates exactly these release artifacts:

```text
dist\NowPlaying.exe
dist\NowPlaying.exe.sha256
```

The EXE uses PyInstaller one-file and windowed modes. HTML, schema, icon, Python modules, WinRT bindings, Pillow, and tray dependencies are embedded.

## Tests

Run the test suite from the repository directory:

```bat
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests and build on pushes to `master`. Tagged releases also attach `NowPlaying.exe` and `NowPlaying.exe.sha256` directly to the GitHub release.

## License

MIT
