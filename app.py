"""
Combined entry point for PyInstaller builds.

Runs the media extractor and the HTTP server in a single process
so users only need to launch one .exe.
"""

import asyncio
import os
import sys
import threading

# When frozen by PyInstaller, the working directory should be where
# the .exe lives, not the temp folder PyInstaller unpacks into.
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(sys.executable)
    os.chdir(_exe_dir)
    # Also fix sys.path so imports of server/nowplaying find the
    # right ROOT when they check getattr(sys, 'frozen', False)
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


def run_server():
    """Start the HTTP server in a background thread."""
    # Import here so the module-level code in server.py uses the right cwd
    sys.argv = [sys.argv[0]]  # strip extra args
    import server
    server.main()


def main():
    print()
    print("  ======================================")
    print("    Now Playing - OBS Overlay")
    print("  ======================================")
    print()

    # Start the HTTP server on a daemon thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Run the extractor on the main thread (needs asyncio)
    import nowplaying
    try:
        asyncio.run(nowplaying.main())
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
