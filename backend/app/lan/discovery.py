from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAGIC = "locflix-lan-v1"
DEFAULT_DISCOVERY_PORT = 8788
ANNOUNCE_INTERVAL_SEC = 2.0
DISCOVER_WINDOW_SEC = 2.5


@dataclass(frozen=True)
class DiscoveredSource:
    seeder_id: str
    name: str
    host: str
    port: int
    base_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seeder_id": self.seeder_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "base_url": self.base_url,
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

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
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
        except OSError:
            logger.exception("LAN discovery bind failed on port %s", self.discovery_port)
            sock.close()
            return

        sock.settimeout(0.5)
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
        for target in (("255.255.255.255", self.discovery_port), ("<broadcast>", self.discovery_port)):
            try:
                sock.sendto(packet, target)
                break
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
        try:
            sock.sendto(encode_packet({"type": "reply", **announce}), addr)
        except OSError:
            logger.debug("Failed to reply to discover from %s", addr)


def scan_lan_sources(*, discovery_port: int = DEFAULT_DISCOVERY_PORT, timeout: float = DISCOVER_WINDOW_SEC) -> list[DiscoveredSource]:
    """Broadcast a discover probe and collect unique seeder announcements."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    sock.settimeout(0.35)
    try:
        sock.bind(("", 0))
    except OSError:
        sock.close()
        return []

    probe = encode_packet({"type": "discover"})
    for target in (("255.255.255.255", discovery_port), ("<broadcast>", discovery_port)):
        try:
            sock.sendto(probe, target)
            break
        except OSError:
            continue

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
        if payload is None:
            continue
        if payload.get("type") not in {"announce", "reply"}:
            continue
        source = _source_from_payload(payload)
        if source is not None:
            found[source.seeder_id] = source

    try:
        sock.close()
    except OSError:
        pass
    return sorted(found.values(), key=lambda s: s.name.lower())


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
