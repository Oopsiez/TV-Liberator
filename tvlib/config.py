"""Persistent app configuration and app catalog.

Stored as JSON under the user's config dir so settings survive restarts.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_dir() -> Path:
    """Return a writable per-user config directory (cross-platform)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "TVLiberator"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "tv-liberator"


@dataclass
class KnownTV:
    """A TV we have discovered or paired with before."""
    vendor: str  # "samsung" | "lg" | "unknown"
    host: str
    name: str = ""
    model: str = ""
    firmware: str = ""
    mac: str = ""
    last_seen: float = 0.0
    paired_token: str = ""  # LG client-key / Samsung token


@dataclass
class AppConfig:
    """Top-level persisted configuration."""
    callback_host: str = ""           # this PC's LAN IP the TV should call back
    dns_listen: str = "0.0.0.0:53"    # network-guard DNS bind
    allowlist: list[str] = field(default_factory=list)  # extra allowed domains
    known_tvs: list[KnownTV] = field(default_factory=list)
    block_updates: bool = True

    @classmethod
    def load(cls) -> "AppConfig":
        p = config_dir() / "config.json"
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        tvs = [KnownTV(**t) for t in data.pop("known_tvs", [])]
        cfg = cls(**data)
        cfg.known_tvs = tvs
        return cfg

    def save(self) -> None:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        (d / "config.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def upsert_tv(self, tv: KnownTV) -> None:
        for i, existing in enumerate(self.known_tvs):
            if existing.host == tv.host:
                # keep a previously stored pairing token if the new one is blank
                if not tv.paired_token and existing.paired_token:
                    tv.paired_token = existing.paired_token
                self.known_tvs[i] = tv
                return
        self.known_tvs.append(tv)


# Curated catalog of installable apps per vendor.
# Samsung apps are Tizen .wgt packages; LG apps are webOS .ipk packages.
# URLs point at official release assets; kept here so the UI can offer
# one-click install of the apps the user actually wants.
APP_CATALOG: dict[str, list[dict]] = {
    "samsung": [
        {
            "id": "jellyfin",
            "name": "Jellyfin",
            "kind": "wgt",
            # Official Jellyfin Tizen build (packaged .wgt).
            "source": "jellyfin-tizen",
            "notes": "Built from official jellyfin-web + jellyfin-tizen.",
        },
    ],
    "lg": [
        {
            "id": "jellyfin",
            "name": "Jellyfin",
            "kind": "ipk",
            "source": "jellyfin-webos",
            "notes": "Official jellyfin-webos .ipk release.",
        },
    ],
}
