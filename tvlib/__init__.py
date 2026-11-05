"""TV Liberator: take back control of your Samsung and LG TVs.

A local app that discovers your TVs, sideloads the apps you actually want
(Jellyfin, YouTube), disables microphones / screen-recognition / telemetry,
blocks firmware auto-updates, and cuts the TVs off the network except for the
traffic you explicitly allow.
"""
from pathlib import Path

def _read_version() -> str:
    vf = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return vf.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"

__version__ = _read_version()
