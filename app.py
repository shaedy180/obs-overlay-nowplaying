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
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


def _get_version():
    vf = os.path.join(os.getcwd(), "version.txt")
    if os.path.isfile(vf):
        with open(vf) as f:
            return f.read().strip()
    return "unknown"


def run_server():
    """Start the HTTP server in a background thread."""
    sys.argv = [sys.argv[0]]  # strip extra args
    import server
    server.main()


def main():
    # Handle --update flag before starting anything else
    if "--update" in sys.argv:
        import update
        update.main()
        return

    version = _get_version()
    print()
    print("  ======================================")
    print(f"    Now Playing - OBS Overlay v{version}")
    print("  ======================================")
    print()

    # Start the HTTP server on a daemon thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Run the extractor on the main thread (needs asyncio)
    try:
        import nowplaying
        asyncio.run(nowplaying.main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except ImportError as exc:
        if "winrt" in str(exc).lower():
            print("\n  [ERROR] WinRT packages are not available.")
            if not getattr(sys, "frozen", False):
                print("  Run: pip install -r requirements.txt")
            else:
                print("  Try re-downloading the latest release.")
        else:
            raise
    except Exception as exc:
        print(f"\n  [ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
