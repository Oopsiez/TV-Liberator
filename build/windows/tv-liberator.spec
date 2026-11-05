# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one folder, sdb + web assets bundled."""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent

datas = [
    (str(ROOT / "tvlib" / "web" / "static"), "tvlib/web/static"),
    (str(ROOT / "VERSION"), "."),
]
sdb_win = ROOT / "tvlib" / "vendor" / "sdb" / "windows"
if sdb_win.is_dir():
    datas.append((str(sdb_win), "tvlib/vendor/sdb/windows"))

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="TV Liberator",
    console=False,
    uac_admin=True,   # network guard binds UDP 53
)
coll = COLLECT(exe, a.binaries, a.datas, name="TV Liberator")
