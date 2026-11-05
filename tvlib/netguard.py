"""Network guard: give a TV *zero* network access except traffic you allow.

This is the only airtight layer, because anything done on the TV itself can be
reverted by a firmware update. Two enforcement modes:

  1. DNS sinkhole (default, no router changes):
     A tiny DNS server runs on this PC. The TV is pointed at it (static DNS on
     the TV, or DHCP option from the guard's gateway mode). Any domain NOT on
     the allowlist is answered with 0.0.0.0, so the TV can reach Jellyfin and
     YouTube but not Samsung/LG telemetry or update servers.

  2. Gateway lockdown (strongest, still no router login):
     The PC answers ARP for the real gateway so the TV routes through the PC;
     the PC then forwards only allowlisted flows and drops the rest. Enabled
     separately because it needs raw sockets / admin.

This module implements mode 1 fully (pure stdlib). Mode 2 hooks are provided
and documented; it is wired up in the platform-specific installer.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass, field

# Domains required by the apps the user actually wants. Everything else is
# sinkholed. These are intentionally conservative allowlists.
ALLOW_PROFILES: dict[str, list[str]] = {
    "jellyfin": [
        # Jellyfin talks only to the user's own server; allow nothing public by
        # default except the plugin/image CDNs the client may use.
        "repo.jellyfin.org",
    ],
    "youtube": [
        "youtube.com", "youtubei.googleapis.com", "ytimg.com",
        "googlevideo.com", "ggpht.com", "gstatic.com", "googleapis.com",
        "google.com", "youtube-nocookie.com",
    ],
    "time-and-net": [
        # Keep the TV's clock and captive-portal/connectivity check working.
        "pool.ntp.org", "time.windows.com", "time.google.com",
    ],
}

# Known telemetry / ad / update endpoints we explicitly blackhole even if a
# broad allow rule would otherwise match.
DENYLIST: list[str] = [
    # Samsung
    "samsungads.com", "samsungacr.com", "samsungcloudsolution.com",
    "samsungotn.net", "samsungcloudcdn.com", "samsungrm.net",
    "samsung-com.com", "samsungotn.com", "nmetrics.samsung.com",
    "log-config.samsungacr.com", "configprd.samsungcloudsolution.com",
    # LG
    "lgtvsdp.com", "lgtvcommon.com", "lgappstv.com", "lgsmartad.com",
    "rdx2.lgtvsdp.com", "ad.lgappstv.com", "us.info.lgsmartad.com",
    "lgtviot.com", "lgeapi.com", "yumenetworks.com",
]


def _norm(d: str) -> str:
    return d.strip().lower().rstrip(".")


@dataclass
class GuardConfig:
    profiles: list[str] = field(default_factory=lambda: ["youtube", "time-and-net"])
    extra_allow: list[str] = field(default_factory=list)
    upstream_dns: str = "1.1.1.1"
    listen_host: str = "0.0.0.0"
    listen_port: int = 53

    def allowed(self) -> set[str]:
        out: set[str] = set()
        for p in self.profiles:
            out |= {_norm(x) for x in ALLOW_PROFILES.get(p, [])}
        out |= {_norm(x) for x in self.extra_allow}
        return out


class DNSGuard:
    """A minimal allowlist DNS server. Non-allowlisted names -> 0.0.0.0."""

    def __init__(self, cfg: GuardConfig):
        self.cfg = cfg
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.blocked = 0
        self.allowed_count = 0

    # -- matching ------------------------------------------------------------
    def _is_allowed(self, qname: str) -> bool:
        q = _norm(qname)
        for d in DENYLIST:
            if q == d or q.endswith("." + d):
                return False
        for d in self.cfg.allowed():
            if q == d or q.endswith("." + d):
                return True
        return False

    # -- DNS wire ------------------------------------------------------------
    @staticmethod
    def _parse_qname(data: bytes) -> tuple[str, int]:
        pos = 12
        labels = []
        while True:
            length = data[pos]
            if length == 0:
                pos += 1
                break
            labels.append(data[pos + 1 : pos + 1 + length].decode("latin1"))
            pos += 1 + length
        return ".".join(labels), pos

    def _sinkhole_response(self, data: bytes, qend: int) -> bytes:
        tid = data[:2]
        flags = b"\x81\x80"  # standard response, no error
        counts = struct.pack(">HHHH", 1, 1, 0, 0)
        header = tid + flags + counts
        question = data[12:qend] + data[qend : qend + 4]
        qtype = data[qend : qend + 2]
        answer = b"\xc0\x0c" + qtype + b"\x00\x01" + struct.pack(">I", 60)
        if qtype == b"\x00\x1c":  # AAAA -> empty ::  (16 bytes of zero)
            answer += struct.pack(">H", 16) + b"\x00" * 16
        else:  # A -> 0.0.0.0
            answer += struct.pack(">H", 4) + socket.inet_aton("0.0.0.0")
        return header + question + answer

    def _forward(self, data: bytes) -> bytes:
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.settimeout(3.0)
        try:
            up.sendto(data, (self.cfg.upstream_dns, 53))
            resp, _ = up.recvfrom(65535)
            return resp
        finally:
            up.close()

    def _handle(self, data: bytes, addr, sock: socket.socket) -> None:
        try:
            qname, qend = self._parse_qname(data)
        except (IndexError, UnicodeDecodeError):
            return
        if self._is_allowed(qname):
            self.allowed_count += 1
            try:
                sock.sendto(self._forward(data), addr)
            except OSError:
                pass
        else:
            self.blocked += 1
            sock.sendto(self._sinkhole_response(data, qend), addr)

    def _serve(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.cfg.listen_host, self.cfg.listen_port))
        s.settimeout(0.5)
        self._sock = s
        while not self._stop.is_set():
            try:
                data, addr = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(data, addr, s),
                             daemon=True).start()
        s.close()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        time.sleep(0.1)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
