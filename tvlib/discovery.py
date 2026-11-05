"""Discover Samsung and LG TVs on the local network.

Strategy (best-effort, no external deps required):
  * SSDP / UPnP M-SEARCH  -> most smart TVs answer, exposing model info URLs.
  * Samsung REST probe     -> http://<host>:8001/api/v2/  returns device + model.
  * LG probe               -> UPnP description + SSAP port 3000/3001 presence.
  * ARP table scan         -> fallback MAC/vendor identification.

The goal is to classify each host as samsung | lg | unknown and attach a
model / firmware string when the device advertises one.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable

SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_MX = 2


@dataclass
class Discovered:
    host: str
    vendor: str = "unknown"
    name: str = ""
    model: str = ""
    firmware: str = ""
    mac: str = ""
    sources: list[str] = field(default_factory=list)


def _ssdp_search(timeout: float = 3.0) -> set[str]:
    """Return hosts that answer an SSDP M-SEARCH."""
    msg = "\r\n".join([
        "M-SEARCH * HTTP/1.1",
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}",
        'MAN: "ssdp:discover"',
        f"MX: {SSDP_MX}",
        "ST: ssdp:all",
        "", "",
    ]).encode()
    hosts: set[str] = set()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(timeout)
    try:
        s.sendto(msg, SSDP_ADDR)
        while True:
            try:
                _data, addr = s.recvfrom(65507)
            except socket.timeout:
                break
            hosts.add(addr[0])
    finally:
        s.close()
    return hosts


def _http_get(url: str, timeout: float = 2.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def _probe_samsung(host: str) -> Discovered | None:
    """Samsung TVs expose a device-info endpoint on 8001."""
    body = _http_get(f"http://{host}:8001/api/v2/")
    if not body:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    dev = data.get("device", {})
    name = dev.get("name") or dev.get("FriendlyName") or ""
    model = dev.get("modelName") or dev.get("model") or ""
    fw = dev.get("firmwareVersion") or dev.get("version") or ""
    return Discovered(host=host, vendor="samsung", name=name, model=model,
                      firmware=fw, mac=dev.get("wifiMac", ""),
                      sources=["samsung-rest"])


def _probe_lg(host: str) -> Discovered | None:
    """LG webOS TVs listen on SSAP ports 3000/3001; model via UPnP desc."""
    open_ssap = False
    for port in (3001, 3000):
        try:
            with socket.create_connection((host, port), timeout=1.0):
                open_ssap = True
                break
        except OSError:
            continue
    if not open_ssap:
        return None
    model = name = fw = ""
    # Try the common UPnP device description locations.
    for path in ("/", "/nrdp/1/DeviceDescription.xml"):
        xml = _http_get(f"http://{host}:1900{path}") or _http_get(
            f"http://{host}:3000{path}")
        if xml and "<modelName" in xml:
            model = _xml_tag(xml, "modelName")
            name = _xml_tag(xml, "friendlyName")
            break
    return Discovered(host=host, vendor="lg", name=name, model=model,
                      firmware=fw, sources=["lg-ssap"])


def _xml_tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.I | re.S)
    return m.group(1).strip() if m else ""


def classify(host: str) -> Discovered:
    """Probe a single host and classify it."""
    return (_probe_samsung(host) or _probe_lg(host)
            or Discovered(host=host, vendor="unknown"))


def scan(extra_hosts: Iterable[str] = ()) -> list[Discovered]:
    """Discover TVs on the LAN. Returns classified results."""
    hosts = set(_ssdp_search()) | set(extra_hosts)
    results: list[Discovered] = []
    for h in sorted(hosts):
        d = classify(h)
        if d.vendor != "unknown":
            results.append(d)
    return results
