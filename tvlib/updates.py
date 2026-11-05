"""Disable firmware / auto-updates so an update can't undo our work.

Three layers, strongest last:

  1. Native setting  - Samsung: vconf `db/menu/support/softwareupdate/autoupdate`
                       -> 0 (the stock menu's Off). LG: auto-update toggle via
                       the dev session.
  2. App/service     - block the updater app paths where we have access.
  3. Network guard   - the decisive one: the vendors' update hosts are on the
                       guard DENYLIST, so firmware simply cannot download even
                       if a setting is reset.

Layer 3 works on every TV regardless of model, root or firmware, which is why
the guard is the backbone of this feature.
"""
from __future__ import annotations

SAMSUNG_AUTOUPDATE_KEY = "db/menu/support/softwareupdate/autoupdate"

# Firmware/update endpoints blocked at the guard.
UPDATE_HOSTS = [
    # Samsung
    "samsungotn.net", "samsungotn.com", "samsungcloudsolution.com",
    "fota-cloud-dn.ospserver.net", "fota-secure-dn.ospserver.net",
    # LG
    "lgtvsdp.com", "rdx2.lgtvsdp.com", "lgeapi.com", "snu.lge.com",
    "update.lgappstv.com",
]


def plan(vendor: str) -> dict:
    """Return the layered plan for disabling updates on a vendor."""
    vendor = vendor.lower()
    layers = [{
        "layer": "network-guard",
        "action": "blackhole firmware/update domains",
        "hosts": UPDATE_HOSTS,
        "reversible": True,
        "works_without_root": True,
    }]
    if vendor == "samsung":
        layers.insert(0, {
            "layer": "native-setting",
            "action": f"set {SAMSUNG_AUTOUPDATE_KEY} = 0 (Auto Update Off)",
            "reversible": True,
            "works_without_root": False,
        })
    elif vendor == "lg":
        layers.insert(0, {
            "layer": "native-setting",
            "action": "turn off automatic software update via dev session",
            "reversible": True,
            "works_without_root": False,
        })
    return {"vendor": vendor, "layers": layers}
