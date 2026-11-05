"""App catalog: preloaded packages, auto-downloaded when not bundled.

The installer bundles each catalog package under tvlib/vendor/apps/. If a
package is missing (portable/dev run), it is downloaded to the system temp
folder. Downloads use GitHub's release-download URLs, not the API, so there is
no rate limit and no token.

Samsung: jeppevinkel/jellyfin-tizen-builds `Jellyfin.wgt` (stable jellyfin-web,
pre-signed, required Tizen 2.3+). LG: jellyfin/jellyfin-webos `.ipk`, resolved
from the release's stable manifest and checked against its sha256.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

TIZEN_DL = "https://github.com/jeppevinkel/jellyfin-tizen-builds/releases/latest/download/"
WEBOS_DL = "https://github.com/jellyfin/jellyfin-webos/releases/latest/download/"

CATALOG: dict[str, dict] = {
    "jellyfin": {
        "name": "Jellyfin",
        "samsung": {"file": "Jellyfin.wgt", "url": TIZEN_DL + "Jellyfin.wgt"},
        "lg": {"manifest": WEBOS_DL + "org.jellyfin.webos.manifest.json",
               "app_id": "org.jellyfin.webos"},
    },
}


class AppStoreError(RuntimeError):
    pass


def bundled_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    root = Path(meipass) / "tvlib" if meipass else Path(__file__).resolve().parent
    return root / "vendor" / "apps"


def download_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "TVLiberator"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _open(url: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": "tv-liberator"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310


def _download(url: str, dest: Path) -> Path:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with _open(url, 300) as r, tmp.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 16), b""):
            f.write(chunk)
    tmp.replace(dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _lg_manifest(entry: dict) -> dict:
    with _open(entry["manifest"], 30) as r:
        return json.loads(r.read().decode())


def catalog(vendor: str) -> list[dict]:
    """Apps installable on this vendor, for the UI dropdown."""
    out = []
    for app_id, app in CATALOG.items():
        if vendor not in app:
            continue
        bundled = any(bundled_dir().glob(f"{vendor}-{app_id}.*"))
        out.append({"id": app_id, "name": app["name"], "bundled": bundled})
    return out


def resolve(app_id: str, vendor: str, dest_dir: Path | None = None) -> Path:
    """Return a local package path: bundled copy, else download it."""
    app = CATALOG.get(app_id)
    if not app or vendor not in app:
        raise AppStoreError(f"{app_id!r} is not available for {vendor}")
    ext = ".wgt" if vendor == "samsung" else ".ipk"
    pre = bundled_dir() / f"{vendor}-{app_id}{ext}"
    if pre.exists() and dest_dir is None:
        return pre
    entry = app[vendor]
    dest = (dest_dir or download_dir()) / f"{vendor}-{app_id}{ext}"
    try:
        if vendor == "samsung":
            return _download(entry["url"], dest)
        man = _lg_manifest(entry)
        _download(WEBOS_DL + man["ipkUrl"], dest)
        want = man.get("ipkHash", {}).get("sha256", "")
        if want and sha256(dest) != want:
            dest.unlink(missing_ok=True)
            raise AppStoreError(f"{app['name']} download failed its sha256 check")
        return dest
    except OSError as e:
        raise AppStoreError(
            f"Could not download {app['name']} for {vendor}: {e}") from e


def bundle_all(dest: Path | None = None) -> list[Path]:
    """Build-time: fetch every catalog package into tvlib/vendor/apps/."""
    d = dest or (Path(__file__).resolve().parent / "vendor" / "apps")
    d.mkdir(parents=True, exist_ok=True)
    return [resolve(a, v, d) for a, app in CATALOG.items()
            for v in ("samsung", "lg") if v in app]


if __name__ == "__main__":
    for p in bundle_all():
        print(p, p.stat().st_size)
