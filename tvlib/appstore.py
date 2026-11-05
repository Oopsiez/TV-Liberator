"""Fetch installable app packages so the user never hunts for a file.

Samsung (.wgt): we use the community jellyfin-tizen-builds releases, which are
pre-signed with a distributor certificate and install on any Developer-Mode
Samsung TV. LG (.ipk): the official jellyfin-webos releases.

Packages are cached under the user's config dir; large binaries are never
committed to the repo.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

from tvlib.config import config_dir

JELLYFIN_TIZEN_API = (
    "https://api.github.com/repos/jeppevinkel/jellyfin-tizen-builds/releases/latest"
)
JELLYFIN_WEBOS_API = (
    "https://api.github.com/repos/jellyfin/jellyfin-webos/releases/latest"
)


def cache_dir() -> Path:
    d = config_dir() / "packages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "tv-liberator"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
        return json.loads(r.read().decode())


def _download(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "tv-liberator"})
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        dest.write_bytes(r.read())
    return dest


def samsung_jellyfin_assets() -> list[dict]:
    """List the .wgt variants available in the latest Tizen build release."""
    rel = _get_json(JELLYFIN_TIZEN_API)
    out = []
    for a in rel.get("assets", []):
        if a["name"].endswith(".wgt"):
            out.append({"name": a["name"], "url": a["browser_download_url"],
                        "size": a["size"], "tag": rel.get("tag_name", "")})
    return out


def fetch_samsung_jellyfin(variant: str = "Jellyfin-10.11.z.wgt") -> Path:
    """Download a specific .wgt variant to the cache and return its path."""
    for a in samsung_jellyfin_assets():
        if a["name"] == variant:
            dest = cache_dir() / a["name"]
            if dest.exists() and dest.stat().st_size == a["size"]:
                return dest
            return _download(a["url"], dest)
    raise FileNotFoundError(f"variant {variant!r} not found in latest release")


def lg_jellyfin_asset() -> dict:
    rel = _get_json(JELLYFIN_WEBOS_API)
    for a in rel.get("assets", []):
        if a["name"].endswith(".ipk"):
            return {"name": a["name"], "url": a["browser_download_url"],
                    "size": a["size"], "tag": rel.get("tag_name", "")}
    raise FileNotFoundError("no .ipk in latest jellyfin-webos release")


def fetch_lg_jellyfin() -> Path:
    a = lg_jellyfin_asset()
    dest = cache_dir() / a["name"]
    if dest.exists() and dest.stat().st_size == a["size"]:
        return dest
    return _download(a["url"], dest)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
