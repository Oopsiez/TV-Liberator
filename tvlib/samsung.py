"""Samsung (Tizen) control via SDB.

This talks to a Samsung TV that has Developer Mode enabled (Apps -> enter
"12345" -> turn on Developer Mode, set the PC's IP, reboot). No account and no
root are required for sideloading and app management; SDB is Samsung's own
Smart Development Bridge.

All calls shell out to the bundled `sdb` binary. On Windows the binary ships in
tvlib/vendor/sdb/<os>/; on dev machines it falls back to PATH.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path

SDB_PORT = 26101


class SamsungError(RuntimeError):
    pass


def _vendor_sdb() -> str | None:
    # PyInstaller unpacks bundled data under sys._MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    root = Path(meipass) / "tvlib" if meipass else Path(__file__).resolve().parent
    base = root / "vendor" / "sdb"
    system = platform.system().lower()
    name = "sdb.exe" if system == "windows" else "sdb"
    cand = base / system / name
    return str(cand) if cand.exists() else None


def sdb_path(explicit: str | None = None) -> str:
    """Resolve the sdb binary: explicit -> env -> bundled -> PATH."""
    for c in (explicit, os.environ.get("SDB"), _vendor_sdb(), shutil.which("sdb")):
        if c and Path(c).exists():
            return c
    if shutil.which("sdb"):
        return "sdb"
    raise SamsungError(
        "sdb not found. Bundle it in tvlib/vendor/sdb or install Tizen Studio."
    )


@dataclass
class SamsungDevice:
    host: str
    serial: str = ""          # sdb device serial (usually host:port)
    model: str = ""
    platform_ver: str = ""    # Tizen version


class Samsung:
    def __init__(self, host: str, sdb: str | None = None):
        self.host = host
        self.sdb = sdb_path(sdb)

    # -- low level -----------------------------------------------------------
    def _run(self, *args: str, timeout: int = 60) -> str:
        proc = subprocess.run(
            [self.sdb, *args], capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            raise SamsungError(
                f"sdb {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout

    def _serial(self) -> str:
        return f"{self.host}:{SDB_PORT}"

    def _dev(self, *args: str, timeout: int = 120) -> str:
        return self._run("-s", self._serial(), *args, timeout=timeout)

    # -- connection ----------------------------------------------------------
    def connect(self) -> SamsungDevice:
        """Connect sdb to the TV. Requires Developer Mode + this PC's IP set."""
        out = self._run("connect", self._serial(), timeout=20)
        if "connected" not in out.lower() and "already" not in out.lower():
            raise SamsungError(
                f"Could not connect to {self.host}. Is Developer Mode on and "
                f"this PC's IP entered on the TV? sdb said: {out.strip()}"
            )
        dev = SamsungDevice(host=self.host, serial=self._serial())
        try:
            cap = self._dev("capability", timeout=20)
            dev.platform_ver = _cap(cap, "platform_version")
            dev.model = _cap(cap, "device_name") or _cap(cap, "model_name")
        except SamsungError:
            pass
        return dev

    def disconnect(self) -> None:
        try:
            self._run("disconnect", self._serial(), timeout=10)
        except SamsungError:
            pass

    # -- apps ----------------------------------------------------------------
    def list_apps(self) -> list[dict]:
        """Return installed apps as {id, name}. Uses the app_launcher query."""
        out = self._dev("shell", "0", "applist", timeout=30)
        apps: list[dict] = []
        for line in out.splitlines():
            # Lines look like: 'App list[0]:  'Name' 'appid''
            m = re.search(r"'([^']*)'\s+'([^']+)'", line)
            if m:
                apps.append({"name": m.group(1), "id": m.group(2)})
        return apps

    def install(self, wgt_path: str) -> str:
        """Sideload a .wgt package onto the TV."""
        p = Path(wgt_path)
        if not p.exists():
            raise SamsungError(f"package not found: {wgt_path}")
        return self._dev("install", str(p), timeout=600)

    def uninstall(self, app_id: str) -> str:
        return self._dev("uninstall", app_id, timeout=120)

    def launch(self, app_id: str) -> str:
        return self._dev("shell", "0", "was_execute", app_id, timeout=30)


def _cap(cap_output: str, key: str) -> str:
    m = re.search(rf"{re.escape(key)}:(.*)", cap_output)
    return m.group(1).strip() if m else ""
