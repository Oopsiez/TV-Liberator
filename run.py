"""Launch the TV Liberator control panel."""
import webbrowser, threading, uvicorn
from tvlib import __version__

PORT = 8777

def main():
    print(f"TV Liberator v{__version__} -> http://127.0.0.1:{PORT}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    uvicorn.run("tvlib.web.app:app", host="127.0.0.1", port=PORT, log_level="info")

if __name__ == "__main__":
    main()
