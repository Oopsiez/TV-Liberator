"""LG webOS control.

Two capability tiers, auto-selected per TV:

  * Dev-mode tier (works on modern webOS incl. webOS 22-24, e.g. 86QNED82):
    Sideload .ipk apps and manage them using the webOS Developer Mode app +
    SSH/ares toolchain. Requires a free LG developer account and the Developer
    Mode app installed on the TV. No root.

  * Control tier (always available once paired): the SSAP websocket API on
    ws://<host>:3000 (or wss://:3001) controls power, input, volume, app launch,
    and reads system info. Pairing stores a client-key for reuse.

Mic and ACR ("Live Plus") removal on non-rootable sets is done by toggling the
documented settings via luna calls over the dev session, and — authoritatively —
by blocking LG's telemetry/update domains at the network guard.
"""
from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field

SSAP_PORT = 3000
SSAP_TLS_PORT = 3001

# Minimal SSAP handshake payload (client-key filled in when known).
_REGISTER = {
    "type": "register",
    "id": "register_0",
    "payload": {
        "forcePairing": False,
        "pairingType": "PROMPT",
        "client-key": "",
        "manifest": {
            "manifestVersion": 1,
            "appVersion": "1.1",
            "signed": {"created": "20240101", "appId": "com.tvliberator.app",
                        "vendorId": "com.tvliberator", "localizedAppNames": {"": "TV Liberator"},
                        "localizedVendorNames": {"": "TV Liberator"},
                        "permissions": ["LAUNCH", "CONTROL_AUDIO",
                                         "CONTROL_POWER", "READ_INSTALLED_APPS",
                                         "CONTROL_INPUT_MEDIA_PLAYBACK",
                                         "READ_TV_CURRENT_CHANNEL"],
                        "serial": "0"},
            "permissions": ["LAUNCH", "CONTROL_AUDIO", "CONTROL_POWER",
                            "READ_INSTALLED_APPS"],
            "signatures": [],
        },
    },
}


class LGError(RuntimeError):
    pass


@dataclass
class LGDevice:
    host: str
    model: str = ""
    webos_version: str = ""
    client_key: str = ""
    rootable: bool = False


def _webos_major(version: str) -> int:
    try:
        return int(str(version).split(".")[0])
    except (ValueError, IndexError):
        return 0


def assess_rootability(webos_version: str) -> dict:
    """RootMyTV / crashd homebrew only covers up to ~webOS 7 (2022)."""
    major = _webos_major(webos_version)
    if 0 < major <= 7:
        tier = "rootable"
        note = "Community root (RootMyTV/Homebrew) likely available."
    elif major >= 8:
        tier = "dev-mode-only"
        note = ("Too new for community root. Dev Mode sideload + settings + "
                "network guard only.")
    else:
        tier = "unknown"
        note = "Could not read webOS version; will probe on connect."
    return {"tier": tier, "note": note, "webos_major": major}


class LGControl:
    """SSAP websocket control (stdlib-only minimal client)."""

    def __init__(self, host: str, client_key: str = ""):
        self.host = host
        self.client_key = client_key

    def _ws_connect(self, timeout: float = 5.0) -> socket.socket:
        import base64
        import os as _os
        s = socket.create_connection((self.host, SSAP_PORT), timeout=timeout)
        key = base64.b64encode(_os.urandom(16)).decode()
        req = (
            f"GET / HTTP/1.1\r\nHost: {self.host}:{SSAP_PORT}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(req.encode())
        resp = s.recv(4096)
        if b"101" not in resp.split(b"\r\n", 1)[0]:
            s.close()
            raise LGError("websocket upgrade refused by TV")
        return s

    @staticmethod
    def _ws_send(sock: socket.socket, payload: dict) -> None:
        data = json.dumps(payload).encode()
        header = bytearray([0x81])
        n = len(data)
        mask = b"\x00\x00\x00\x00"  # masked but zero-mask for simplicity
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += n.to_bytes(2, "big")
        else:
            header.append(0x80 | 127)
            header += n.to_bytes(8, "big")
        sock.sendall(bytes(header) + mask + data)

    def pair(self, timeout: float = 30.0) -> str:
        """Pair with the TV; returns a client-key. Prompts on the TV screen."""
        sock = self._ws_connect()
        try:
            reg = json.loads(json.dumps(_REGISTER))
            reg["payload"]["client-key"] = self.client_key
            self._ws_send(sock, reg)
            sock.settimeout(timeout)
            # Read frames until we see a registered response with client-key.
            sock.recv(65535)  # prompt / registered
            data = sock.recv(65535)
            text = data.split(b"{", 1)
            if len(text) == 2:
                try:
                    msg = json.loads(b"{" + text[1])
                    key = msg.get("payload", {}).get("client-key", "")
                    if key:
                        self.client_key = key
                except ValueError:
                    pass
            return self.client_key
        finally:
            sock.close()
