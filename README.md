# Now Playing — OBS Overlay

A clean, glass-style "Now Playing" overlay for OBS Studio that reads from
Windows Media Controls (GSMTC). Works with Apple Music, Spotify, browsers,
and any application that registers with the Windows media transport layer.

---

## Features

- **Automatic media detection** — reads whatever is playing via the Windows
  Global System Media Transport Controls API (no app-specific hacks).
- **Album art** extracted from the active media session, displayed as a
  rounded thumbnail.
- **Dynamic accent colour** — the dominant colour is pulled from the album
  art and used for the equaliser bars and glow. Can be overridden with a
  fixed colour.
- **Animated equaliser bars** while playing; a pause icon when paused;
  flat bars when idle.
- **Marquee scroll** for long titles that exceed the pill width.
- **Crossfade transition** on track changes (opacity + vertical slide).
- **Glassmorphism pill** with configurable blur, border, background
  transparency, and corner radius.
- **Settings panel** (`settings.html`) — a visual editor for every
  customisation option. Changes are saved to `settings.json` and applied
  to the overlay in real time.
- **One-click launcher** (`start.bat`) — creates a virtualenv, installs
  dependencies, and starts both the extractor and the HTTP server.


## Requirements

- Windows 10 / 11
- Python 3.10 or newer
- OBS Studio (or any application that can load a Browser Source)


## Quick Start

### Option A — double-click

1. Double-click **`start.bat`**.
2. It will create a virtual environment, install dependencies, start the
   media extractor, and start the HTTP server automatically.
3. The console will show the URLs to use.

### Option B — manual (two terminals)

```
cd obs-overlay-nowplaying

# Terminal 1 — create environment and start extractor
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python nowplaying.py

# Terminal 2 — start HTTP server
venv\Scripts\python server.py
```


## OBS Setup

1. In OBS, add a **Browser Source**.
2. Set the URL to `http://127.0.0.1:8000/overlay.html`.
3. Set width to **480** and height to **120** (or adjust to taste).
4. Optionally enable *Refresh browser when scene becomes active*.
5. The background is transparent — the pill composites directly over your
   scene.


## Settings Panel

Open `http://127.0.0.1:8000/settings.html` in any browser while the server
is running. The panel includes:

| Section      | Options                                                          |
|--------------|------------------------------------------------------------------|
| Layout       | Overlay width, corner radius, album art size and radius          |
| Colors       | Pill background (rgba), blur strength, border colour, text       |
|              | colour, accent colour mode (auto from cover / fixed), fixed      |
|              | accent colour picker                                             |
| Typography   | Title size, artist size, artist opacity, marquee speed, font     |
| Visibility   | Show/hide album art, equaliser, artist line, album in artist     |
|              | line; hide overlay when paused; hide overlay when idle           |

Changes are written to `settings.json`. The overlay reloads settings
automatically every few seconds, or instantly when using the settings panel
(which pushes updates via `postMessage`).

A live preview of the overlay is embedded at the top of the settings page.


## File Overview

```
obs-overlay-nowplaying/
  nowplaying.py       Python extractor — polls GSMTC, writes nowplaying.json + cover.jpg
  server.py           HTTP server with no-cache headers and POST endpoint for settings
  overlay.html        The overlay itself — glass pill, EQ bars, pause icon, crossfade
  settings.html       Visual settings panel with live preview
  settings.json       Persisted customisation (auto-generated on first save)
  start.bat           One-click launcher for Windows
  requirements.txt    Python dependencies (winrt packages)
```


## How It Works

1. `nowplaying.py` uses the `winrt` Python bindings to access the Windows
   GSMTC session manager. Every 0.5 seconds it reads the current media
   session (title, artist, album, playback status) and writes
   `nowplaying.json`. When the track changes it also extracts the album
   art thumbnail and saves it as `cover.jpg`.

2. `server.py` is a minimal HTTP server that serves the project folder on
   `127.0.0.1:8000` with no-cache headers (so the overlay always gets
   fresh data). It also exposes `POST /save-settings` so the settings
   panel can persist changes.

3. `overlay.html` polls `nowplaying.json` every 500 ms. On each tick it
   updates the text, loads cover art, extracts the dominant colour, and
   manages the play/pause/idle visual state. It reads `settings.json` on
   startup and every few seconds for customisation values.

4. `settings.html` is a standalone page that reads and writes
   `settings.json` through the server. It also sends live updates to the
   embedded preview iframe via `postMessage`, so you see changes before
   saving.


## Troubleshooting

**Nothing shows up in the overlay**
Make sure media is actually playing. The overlay hides itself when nothing
is detected. Check that `nowplaying.json` exists and contains track data
(open it in a text editor, or visit `http://127.0.0.1:8000/nowplaying.json`).

**Album art is missing**
Some applications do not provide thumbnails through the Windows media API.
The overlay will show a placeholder note icon in that case.

**The extractor crashes on startup**
Make sure you installed the dependencies into the virtual environment:
```
venv\Scripts\pip install -r requirements.txt
```

**Port 8000 is in use**
Pass a different port: `venv\Scripts\python server.py 9000`, and update the
OBS Browser Source URL accordingly.


## License

MIT
