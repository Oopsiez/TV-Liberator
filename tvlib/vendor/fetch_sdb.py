"""Download Samsung's SDB binary so the installer can bundle it.

SDB ships in Samsung's public Tizen Studio binary repo. We pull just the sdb
package (a few MB) rather than the whole SDK, so the user never installs Tizen
Studio.
"""
from __future__ import annotations

import io
import platform
import re
import urllib.request
import zipfile
from pathlib import Path

BASE = "http://download.tizen.org/sdk/tizenstudio/official/binary/"
VENDOR = Path(__file__).resolve().parent / "sdb"


def _index() -> str:
    with urllib.request.urlopen(BASE, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8", "replace")


def latest_sdb_package(os_tag: str) -> str:
    """Find the newest sdb_<ver>_<os_tag>.zip in the public index."""
    names = re.findall(rf'href="(sdb_[^"]*{re.escape(os_tag)}\.zip)"', _index())
    if not names:
        raise FileNotFoundError(f"no sdb package for {os_tag}")
    return sorted(names)[-1]


def fetch(os_tag: str = "windows-64", dest: Path | None = None) -> Path:
    """Download and extract sdb for the given platform tag."""
    pkg = latest_sdb_package(os_tag)
    target = dest or (VENDOR / ("windows" if "windows" in os_tag else "linux"))
    target.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(BASE + pkg, timeout=300) as r:  # noqa: S310
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            name = Path(member).name
            if name in ("sdb", "sdb.exe") or name.endswith((".dll", ".so")):
                out = target / name
                out.write_bytes(z.read(member))
                out.chmod(0o755)
    return target


def default_os_tag() -> str:
    return "windows-64" if platform.system() == "Windows" else "ubuntu-64"


if __name__ == "__main__":
    print("sdb ->", fetch(default_os_tag()))
