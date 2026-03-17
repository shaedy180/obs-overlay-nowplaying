# Roadmap

Things done and things planned to make the tool easier to install, use, and customize.

## Installation

- [x] Preflight checks in the launcher (Python found? correct version? port free? WinRT ok?)
- [x] Clear error messages with concrete next steps
- [x] Auto-open settings page in the browser after start
- [x] Remove hardcoded user paths from start.bat

## Running

- [x] Status / diagnostics page (server running, extractor running, last track, cover status)
- [x] Show which app is providing the media info (Spotify, Apple Music, browser, etc.)
- [x] Copy OBS URL button
- [ ] System tray app or small control window
- [ ] Start/stop/restart from the UI
- [ ] Auto-start with Windows (optional)
- [x] Port selection from diagnostics page

## Settings panel

- [x] Dirty state indicator ("unsaved changes")
- [x] Presets (Minimal, Neon, Glass, Compact)
- [x] Import / export settings as JSON file
- [x] "Revert to last saved" button
- [x] Basic / advanced mode toggle
- [x] Input validation for rgba and font fields

## Overlay

- [x] Demo mode with a sample track (for setup without music playing)
- [x] Gradient fallback when no cover art is available
- [x] Dim overlay on pause instead of hiding completely (optional)
- [x] Subtle highlight flash on track change
- [x] Source app label in debug mode
- [x] Consistent defaults between code and saved config

## Documentation

- [x] Rewrite README for humans, not robots
- [x] 90-second quickstart at the top
- [ ] Short video or GIF walkthrough

## Future ideas

- [ ] Portable mode (no venv knowledge required)
- [ ] Signed release ZIP with bundled Python
- [ ] Multiple overlay layouts (horizontal, vertical, minimal text-only)
- [ ] OBS WebSocket integration for automatic scene switching
- [ ] Localization (German, etc.)
