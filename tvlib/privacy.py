"""Privacy / cleaning actions: microphone and screen-recognition (ACR) off.

The depth available depends on the TV:
  * Samsung with SDB  -> disable the voice/ACR apps and settings on-device.
  * LG dev-mode       -> toggle documented luna settings over the dev session.
  * Any TV            -> authoritative block of mic-cloud / ACR domains at the
                         network guard (see netguard.DENYLIST).

This module records intended actions and, where a live connection exists,
executes the on-device part. Everything here is reversible.
"""
from __future__ import annotations

# Samsung on-device settings keys (vconf) that gate mic + ACR, where reachable.
SAMSUNG_PRIVACY_KEYS = {
    "voice_recognition": "db/menu/system/voice/recognition",
    "acr_viewing_info": "db/menu/support/viewinginformation",
    "interest_based_ads": "db/menu/support/interestbasedadvertising",
    "auto_update": "db/menu/support/softwareupdate/autoupdate",
}

# LG luna settings toggles for mic + ACR ("Live Plus") + ads.
LG_PRIVACY_SETTINGS = {
    "live_plus": ("com.webos.service.config", {"category": "option",
                 "settings": {"livePlus": False}}),
    "voice_recognition": ("com.webos.service.config", {"category": "option",
                 "settings": {"voiceRecognition": False}}),
    "ad_opt_out": ("com.webos.service.config", {"category": "option",
                 "settings": {"advertisingId": ""}}),
}


def samsung_privacy_plan() -> list[dict]:
    return [
        {"key": k, "vconf": v, "set": "0"} for k, v in SAMSUNG_PRIVACY_KEYS.items()
    ]


def lg_privacy_plan() -> list[dict]:
    return [
        {"name": name, "service": svc, "payload": payload}
        for name, (svc, payload) in LG_PRIVACY_SETTINGS.items()
    ]
