from __future__ import annotations

import json
import logging
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from app.lan.netinfo import broadcast_targets, primary_lan_ip

logger = logging.getLogger(__name__)

MAGIC = "locflix-lan-v1"
DEFAULT_DISCOVERY_PORT = 8788
ANNOUNCE_INTERVAL_SEC = 1.5
DISCOVER_WINDOW_SEC = 2.0
HTTP_PROBE_TIMEOUT_SEC = 0.45
HTTP_SCAN_WORKERS = 64


@dataclass(frozen=True)
class DiscoveredSource:
    seeder_id: str
    name: str
    host: str
    port: int
    base_url: str
    is_self: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "seeder_id": self.seeder_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "base_url": self.base_url,
            "is_self": self.is_self,
        }


def encode_packet(payload: dict[str, Any]) -> bytes:
    body = {"magic": MAGIC, **payload}
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def decode_packet(data: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("magic") != MAGIC:
        return None
    return payload


class DiscoveryBeacon:
    """UDP announce loop so leechers can find this seeder on the LAN."""

    def __init__(
        self,
        *,
        discovery_port: int,
        get_announce: Callable[[], dict[str, Any] | None],
    ) -> None:
        self.discovery_port = discovery_port
        self._get_announce = get_announce
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self.last_error = None
        self._thread = threading.Thread(target=self._run, name="locflix-lan-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._sock = None

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            pass
        try:
            sock.bind(("", self.discovery_port))
        except OSError as exc:
            self.last_error = f"UDP bind failed on {self.discovery_port}: {exc}"
            logger.exception("LAN discovery bind failed on port %s", self.discovery_port)
            sock.close()
            return

        sock.settimeout(0.4)
        self._sock = sock
        last_announce = 0.0
        logger.info("LAN discovery listening on UDP %s", self.discovery_port)

        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_announce >= ANNOUNCE_INTERVAL_SEC:
                self._broadcast_announce(sock)
                last_announce = now
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                continue
            self._handle_packet(sock, data, addr)

        try:
            sock.close()
        except OSError:
            pass
        self._sock = None

    def _announce_payload(self) -> dict[str, Any] | None:
        return self._get_announce()

    def _broadcast_announce(self, sock: socket.socket) -> None:
        payload = self._announce_payload()
        if payload is None:
            return
        packet = encode_packet({"type": "announce", **payload})
        for host in broadcast_targets(str(payload.get("host") or primary_lan_ip())):
            try:
                sock.sendto(packet, (host, self.discovery_port))
            except OSError:
                continue

    def _handle_packet(self, sock: socket.socket, data: bytes, addr: tuple[str, int]) -> None:
        payload = decode_packet(data)
        if payload is None:
            return
        if payload.get("type") != "discover":
            return
        announce = self._announce_payload()
        if announce is None:
            return
        reply = encode_packet({"type": "reply", **announce})
        try:
            sock.sendto(reply, addr)
        except OSError:
            logger.debug("Failed to reply to discover from %s", addr)
        # Also re-broadcast so other listeners can hear us.
        self._broadcast_announce(sock)


def scan_lan_sources(
    *,
    discovery_port: int = DEFAULT_DISCOVERY_PORT,
    api_port: int = 8787,
    timeout: float = DISCOVER_WINDOW_SEC,
    hints: list[tuple[str, int]] | None = None,
) -> list[DiscoveredSource]:
    """Find seeders via UDP (best-effort) plus HTTP LAN scan (reliable on Wi‑Fi)."""
    found: dict[str, DiscoveredSource] = {}

    for source in _scan_udp(discovery_port=discovery_port, timeout=timeout):
        found[source.seeder_id] = source

    # Wi‑Fi APs often block UDP broadcast even when TCP streaming works.
    for source in scan_http_lan(api_port=api_port, hints=hints):
        found[source.seeder_id] = source

    return sorted(found.values(), key=lambda s: s.name.lower())


def _scan_udp(*, discovery_port: int, timeout: float) -> list[DiscoveredSource]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    sock.settimeout(0.25)
    try:
        sock.bind(("", 0))
    except OSError:
        sock.close()
        return []

    probe = encode_packet({"type": "discover"})
    targets = [(host, discovery_port) for host in broadcast_targets()]
    for _ in range(3):
        for target in targets:
            try:
                sock.sendto(probe, target)
            except OSError:
                continue
        time.sleep(0.12)

    found: dict[str, DiscoveredSource] = {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data, _addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        payload = decode_packet(data)
        if payload is None or payload.get("type") not in {"announce", "reply"}:
            continue
        source = _source_from_payload(payload)
        if source is not None:
            found[source.seeder_id] = source

    try:
        sock.close()
    except OSError:
        pass
    return list(found.values())


def neighbor_ips() -> list[str]:
    """IPs seen in the ARP table (recent LAN neighbors)."""
    try:
        completed = subprocess.run(
            ["arp", "-a"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", completed.stdout or "")
    local = primary_lan_ip()
    out: list[str] = []
    seen: set[str] = set()
    for ip in ips:
        if ip.startswith("255.") or ip.endswith(".255") or ip.startswith("224."):
            continue
        if ip in seen:
            continue
        seen.add(ip)
        out.append(ip)
    if local and local not in seen:
        out.insert(0, local)
    return out


def subnet_host_ips(ip: str | None = None) -> list[str]:
    """All hosts in the /24 of the given (or primary) LAN IP."""
    addr = ip or primary_lan_ip()
    parts = addr.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return []
    prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
    return [f"{prefix}.{i}" for i in range(1, 255)]


def scan_http_lan(
    *,
    api_port: int = 8787,
    hints: list[tuple[str, int]] | None = None,
) -> list[DiscoveredSource]:
    """
    Probe LAN hosts over HTTP for a live Locflix seeder.

    This is the reliable path on consumer Wi‑Fi where UDP broadcast is filtered.
    Hints / ARP neighbors are probed first; full /24 only if nothing is found.
    """
    found: dict[str, DiscoveredSource] = {}

    priority: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    def _add(host: str, port: int) -> None:
        key = (host.strip(), int(port))
        if not key[0] or key in seen:
            return
        seen.add(key)
        priority.append(key)

    for host, port in hints or []:
        _add(host, port)
    for ip in neighbor_ips():
        _add(ip, api_port)
    _add(primary_lan_ip(), api_port)

    found.update(_probe_hosts(priority))
    if found:
        return list(found.values())

    # Slow path: full subnet sweep when Wi‑Fi hid everyone from ARP.
    subnet: list[tuple[str, int]] = []
    for ip in subnet_host_ips():
        key = (ip, api_port)
        if key not in seen:
            subnet.append(key)
    found.update(_probe_hosts(subnet))
    return list(found.values())


def _probe_hosts(hosts: list[tuple[str, int]]) -> dict[str, DiscoveredSource]:
    found: dict[str, DiscoveredSource] = {}
    if not hosts:
        return found

    def _check(item: tuple[str, int]) -> DiscoveredSource | None:
        host, port = item
        return probe_http_seeder(host, port, timeout=HTTP_PROBE_TIMEOUT_SEC)

    with ThreadPoolExecutor(max_workers=HTTP_SCAN_WORKERS) as pool:
        futures = [pool.submit(_check, item) for item in hosts]
        for fut in as_completed(futures):
            try:
                source = fut.result()
            except Exception:  # noqa: BLE001
                continue
            if source is not None:
                found[source.seeder_id] = source
    return found


def probe_http_seeder(host: str, port: int, timeout: float = 1.2) -> DiscoveredSource | None:
    """Confirm a host is a live Locflix seeder via /api/lan/status."""
    url = f"http://{host}:{int(port)}/api/lan/status"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("share_enabled") or not data.get("owner_consented"):
        return None
    seeder_id = str(data.get("seeder_id") or "").strip()
    name = str(data.get("share_name") or host).strip()
    lan_ip = str(data.get("lan_ip") or host).strip()
    api_port = int(data.get("api_port") or port)
    if not seeder_id:
        return None
    return DiscoveredSource(
        seeder_id=seeder_id,
        name=name,
        host=lan_ip,
        port=api_port,
        base_url=f"http://{lan_ip}:{api_port}",
    )


def _source_from_payload(payload: dict[str, Any]) -> DiscoveredSource | None:
    seeder_id = str(payload.get("seeder_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    host = str(payload.get("host") or "").strip()
    try:
        port = int(payload.get("port") or 0)
    except (TypeError, ValueError):
        return None
    if not seeder_id or not name or not host or port <= 0:
        return None
    if not payload.get("share_enabled", True):
        return None
    return DiscoveredSource(
        seeder_id=seeder_id,
        name=name,
        host=host,
        port=port,
        base_url=f"http://{host}:{port}",
    )
