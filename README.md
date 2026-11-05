# TV Liberator

A local Windows app that takes your Samsung and LG TVs back: install the apps
you actually want, kill the microphone and screen-recognition, block firmware
updates, and cut the TVs off the network except for traffic you allow.

Runs entirely on your PC. Nothing is sent anywhere.

---

## What it can and cannot do

**It does not flash a custom OS, and no tool can.** Samsung and LG TVs boot from
firmware signed with a key burned into the SoC's one-time-programmable e-fuses.
The mask-ROM first stage only runs a bootloader signed by the vendor, each stage
verifies the next, there is no "disable secure boot" switch, and there is no
community bootloader port for these SoCs. Erasing the signed firmware leaves the
TV with nothing it will boot — a brick with no user-reachable recovery.

So TV Liberator does the thing that actually works: it controls the OS that is
already running, and enforces the rest at the network layer.

| Goal | How it's achieved | Needs root? |
| --- | --- | --- |
| Install Jellyfin / your own apps | Samsung SDB sideload (`.wgt`), LG Dev Mode (`.ipk`) | No |
| Hide every other app / store | Disable app launch on-device | Samsung: no |
| Microphone off | Disable voice apps + services/settings | Depends on model |
| Screen recognition (ACR) off | Disable recognition services/settings | Depends on model |
| Block firmware updates | Native setting **+ blackhole update domains** | Network layer: no |
| Zero network access except what you allow | **Network guard (default-deny DNS)** | No |

The network guard is the backbone: it works on every model regardless of
firmware or root, and a firmware update cannot undo it.

## Per-TV capability

The app detects each TV and tells you what that specific set supports:

- **Samsung (any modern model)** — Developer Mode + SDB. Sideload and app
  management with **no account and no root**. This is the
  "enable dev mode, type the IP, click install" flow.
- **LG webOS ≤ 7 (through ~2022)** — community root (RootMyTV/Homebrew) is
  usually available; deepest cleaning.
- **LG webOS ≥ 8 (2023+, e.g. 86QNED82AAA on webOS 24)** — too new to root.
  You still get Dev Mode sideloading, the mic/ACR settings toggles, and the
  full network lockdown.

## Network guard

A default-deny DNS server runs on your PC. Point the TV's DNS at your PC's LAN
IP and anything not explicitly allowed resolves to `0.0.0.0`.

Verified behaviour:

```
www.youtube.com            -> 142.251.152.4   allowed
time.google.com            -> 216.239.35.0    allowed
samsungads.com             -> 0.0.0.0         blocked
lgsmartad.com              -> 0.0.0.0         blocked
samsungotn.net             -> 0.0.0.0         blocked (Samsung firmware)
rdx2.lgtvsdp.com           -> 0.0.0.0         blocked (LG firmware)
random-tracker.example.com -> 0.0.0.0         blocked (default-deny)
```

Vendor telemetry/ad/update domains are on a denylist that overrides any allow
rule, so you cannot accidentally re-enable them.

For true "zero access" there is an optional **gateway lockdown** mode where the
PC answers ARP for the router so the TV routes through it and only allowlisted
flows are forwarded. A single router/VLAN rule is the strongest equivalent if
you prefer to do it there.

## Setup

### Samsung
1. On the TV: **Apps** → type **12345** → turn on **Developer Mode** → enter
   your PC's LAN IP → reboot.
2. In TV Liberator: **Scan network**, pick the TV, **Install Jellyfin**.

### LG
1. Install **Developer Mode** from the LG Content Store, sign in with a free LG
   developer account, enable Dev Mode and **Key Server**.
2. In TV Liberator: pair, then install the Jellyfin `.ipk`.

LG dev sessions expire about every 50 hours on non-rooted sets and need
renewing — unavoidable without root.

## Running from source

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

Then open <http://127.0.0.1:8777>.

## Tests

```sh
.venv/bin/python -m unittest discover -s tvlib/tests -t . -v
```

## Reversing everything

Every on-device change is reversible, and the network guard is just a process —
stop it and the TV talks to the world again. Re-enable vendor updates by
stopping the guard and turning the native Auto Update setting back on.
