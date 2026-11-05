"""Launch the TV Liberator control panel."""
import sys
import threading
import webbrowser

from tvlib import __version__
from tvlib.config import config_dir

PORT = 8777


def _ensure_streams() -> None:
    # A windowed (no-console) Windows build has sys.stdout/stderr = None,
    # which crashes uvicorn's logging setup. Send output to a log file.
    if sys.stdout is None or sys.stderr is None:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        log = open(d / "tv-liberator.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log


def main():
    _ensure_streams()
    import uvicorn
    from tvlib.web.app import app

    print(f"TV Liberator v{__version__} -> http://127.0.0.1:{PORT}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info", use_colors=False)


if __name__ == "__main__":
    main()
