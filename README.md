# Now Playing for OBS

A small "now playing" overlay for OBS that shows what you're listening to.
It reads from Windows media controls, so it works with Spotify, Apple Music,
browsers, and pretty much anything that shows up in the Windows volume flyout.

![Glass pill overlay with album art, title, artist, and animated EQ bars](https://via.placeholder.com/480x120.png?text=Now+Playing+Overlay)


## Quickstart

1. Double-click `start.bat`.
2. It sets up a Python venv, installs deps, and starts everything.
3. In OBS, add a **Browser Source** with URL `http://127.0.0.1:8000/overlay.html`,
   width 480, height 120.  Done.

The settings page opens automatically in your browser after launch.


## What it does

- Reads the currently playing track via the Windows GSMTC API (no Spotify
  API key, no login, nothing to configure)
- Shows title, artist, album art in a translucent glass pill
- Pulls the accent color from the album cover automatically
- Animated equalizer bars while playing, pause icon when paused
- Scrolls long titles with a marquee
- Crossfade animation on track changes
- Built-in demo mode for setting things up without music playing
- Presets for quick styling (Minimal, Neon, Glass, Compact)
- Everything is configurable through a visual settings panel


## Requirements

- Windows 10 or 11
- Python 3.10+
- OBS Studio (or anything with a browser source)


## Manual setup

If you don't want to use `start.bat`, open two terminals:

```
# Terminal 1: create venv and start the media extractor
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python nowplaying.py

# Terminal 2: start the web server
venv\Scripts\python server.py
```


## OBS setup

1. Add a **Browser Source** in OBS.
2. Set the URL to `http://127.0.0.1:8000/overlay.html`.
3. Set width to **480** and height to **120** (adjust to taste).
4. Optional: enable "Refresh browser when scene becomes active".
5. The background is transparent, so the pill just sits on top of your scene.

You can copy the URL directly from the diagnostics page at
`http://127.0.0.1:8000/status.html`.


## Settings

Open `http://127.0.0.1:8000/settings.html` while the server is running.
The page has a live preview at the top. Any change you make shows up
immediately.

You can tweak layout, colors, blur, typography, visibility, and more.
There are built-in presets if you want a quick starting point, and you can
import/export your settings as a JSON file.


## Files

| File              | What it does                                          |
|-------------------|-------------------------------------------------------|
| `nowplaying.py`   | Polls Windows media controls, writes `nowplaying.json` and `cover.jpg` |
| `server.py`       | Local HTTP server with no-cache headers and a settings save endpoint |
| `overlay.html`    | The overlay (glass pill, EQ bars, crossfade, demo mode) |
| `settings.html`   | Visual settings editor with live preview and presets  |
| `status.html`     | Diagnostics page (health checks, OBS URL, last track) |
| `settings.json`   | Your saved settings (auto-generated)                  |
| `start.bat`       | One-click launcher                                    |
| `requirements.txt`| Python dependencies (winrt packages)                  |


## How it works

`nowplaying.py` uses Python winrt bindings to talk to the Windows media
session manager. Every half second it checks what's playing, writes the
info to `nowplaying.json`, and saves the album art as `cover.jpg` when
the track changes.

`server.py` serves the project folder on localhost:8000 with no-cache
headers. It also has a POST endpoint so the settings panel can save
changes.

`overlay.html` polls `nowplaying.json` every 500ms, updates the display,
extracts the dominant color from the cover art, and handles all the
animations. It picks up settings changes automatically.

`settings.html` reads and writes settings through the server and pushes
live updates to the preview iframe so you see changes before saving.


## Troubleshooting

**Nothing shows up in the overlay**
Make sure something is actually playing. The overlay hides itself when
idle. Check if `nowplaying.json` has data by opening
`http://127.0.0.1:8000/nowplaying.json` in your browser, or check the
diagnostics page at `http://127.0.0.1:8000/status.html`.

**Album art is missing**
Some apps don't provide album art through the Windows media API.
The overlay shows a gradient placeholder in that case.

**The extractor crashes on startup**
Make sure the dependencies are installed:
```
venv\Scripts\pip install -r requirements.txt
```

**Port 8000 is already taken**
Pass a different port: `venv\Scripts\python server.py 9000`, then update
the OBS browser source URL to match.


## License

MIT
