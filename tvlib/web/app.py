"""Local web control panel for TV Liberator.

Runs entirely on the user's PC. Open http://127.0.0.1:8777 after launching.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tvlib import (__version__, appstore, discovery, lg, netguard, privacy,
                   samsung, updates)
from tvlib.config import APP_CATALOG, AppConfig, KnownTV

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="TV Liberator", version=__version__)
_cfg = AppConfig.load()
_guard = netguard.DNSGuard(netguard.GuardConfig())


class HostBody(BaseModel):
    host: str


class InstallBody(BaseModel):
    host: str
    package_path: str


class GuardBody(BaseModel):
    profiles: list[str] | None = None
    extra_allow: list[str] | None = None


@app.get("/api/version")
def version() -> dict:
    return {"version": __version__}


@app.get("/api/catalog")
def catalog() -> dict:
    return APP_CATALOG


@app.post("/api/discover")
def discover() -> dict:
    found = discovery.scan()
    out = []
    for d in found:
        tv = KnownTV(vendor=d.vendor, host=d.host, name=d.name,
                     model=d.model, firmware=d.firmware, mac=d.mac)
        _cfg.upsert_tv(tv)
        item = d.__dict__.copy()
        if d.vendor == "lg":
            item["capability"] = lg.assess_rootability(d.firmware)
        else:
            item["capability"] = {
                "tier": "dev-mode",
                "note": "Enable Developer Mode (Apps -> 12345) and enter this PC's IP.",
            }
        out.append(item)
    _cfg.save()
    return {"tvs": out}


@app.post("/api/samsung/connect")
def samsung_connect(body: HostBody) -> dict:
    try:
        dev = samsung.Samsung(body.host).connect()
    except samsung.SamsungError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return dev.__dict__


@app.post("/api/samsung/apps")
def samsung_apps(body: HostBody) -> dict:
    try:
        s = samsung.Samsung(body.host)
        s.connect()
        return {"apps": s.list_apps()}
    except samsung.SamsungError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/samsung/install")
def samsung_install(body: InstallBody) -> dict:
    try:
        s = samsung.Samsung(body.host)
        s.connect()
        return {"output": s.install(body.package_path)}
    except samsung.SamsungError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/privacy/plan/{vendor}")
def privacy_plan(vendor: str) -> dict:
    if vendor == "samsung":
        return {"plan": privacy.samsung_privacy_plan()}
    if vendor == "lg":
        return {"plan": privacy.lg_privacy_plan()}
    raise HTTPException(status_code=404, detail="unknown vendor")


@app.get("/api/updates/plan/{vendor}")
def updates_plan(vendor: str) -> dict:
    return updates.plan(vendor)


@app.get("/api/guard/status")
def guard_status() -> dict:
    return {
        "running": _guard.running,
        "blocked": _guard.blocked,
        "allowed": _guard.allowed_count,
        "profiles": _guard.cfg.profiles,
        "extra_allow": _guard.cfg.extra_allow,
        "allowed_domains": sorted(_guard.cfg.allowed()),
        "denylist": netguard.DENYLIST,
    }


@app.post("/api/guard/start")
def guard_start(body: GuardBody) -> dict:
    if body.profiles is not None:
        _guard.cfg.profiles = body.profiles
    if body.extra_allow is not None:
        _guard.cfg.extra_allow = body.extra_allow
    try:
        _guard.start()
    except OSError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not bind DNS port {_guard.cfg.listen_port}: {e}. "
                   "Run as Administrator or free port 53.",
        ) from e
    return guard_status()


@app.post("/api/guard/stop")
def guard_stop() -> dict:
    _guard.stop()
    return guard_status()


class InstallAppBody(BaseModel):
    host: str
    vendor: str = "samsung"
    variant: str = "Jellyfin-10.11.z.wgt"


@app.get("/api/apps/samsung/jellyfin")
def samsung_jellyfin_variants() -> dict:
    try:
        return {"variants": appstore.samsung_jellyfin_assets()}
    except Exception as e:  # network/rate-limit
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/api/apps/install")
def install_app(body: InstallAppBody) -> dict:
    """Fetch the chosen app package, then sideload it onto the TV."""
    try:
        if body.vendor == "samsung":
            pkg = appstore.fetch_samsung_jellyfin(body.variant)
            s = samsung.Samsung(body.host)
            s.connect()
            out = s.install(str(pkg))
            return {"package": pkg.name, "sha256": appstore.sha256(pkg),
                    "output": out}
        raise HTTPException(status_code=400,
                            detail="LG install runs through the dev-mode flow")
    except samsung.SamsungError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (OSError, FileNotFoundError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
