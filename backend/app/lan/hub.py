from __future__ import annotations

import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.lan.discovery import (
    DEFAULT_DISCOVERY_PORT,
    DiscoveryBeacon,
    DiscoveredSource,
    probe_http_seeder,
    scan_lan_sources,
)
from app.lan.netinfo import default_share_name, local_hostname, primary_lan_ip, resolve_hostname


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GENERIC_DEVICE_NAMES = {
    "locflix leecher",
    "unknown device",
    "chrome browser",
    "edge browser",
    "firefox browser",
    "safari browser",
}


@dataclass
class LanSession:
    session_id: str
    token: str
    device_name: str
    device_id: str
    client_ip: str
    status: str  # pending | approved | denied | revoked
    created_at: str
    updated_at: str
    last_seen_at: str | None = None
    now_playing_id: str | None = None
    now_playing_title: str | None = None
    hostname: str | None = None

    def to_public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "device_name": self.device_name,
            "hostname": self.hostname,
            "device_id": self.device_id,
            "client_ip": self.client_ip,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_seen_at": self.last_seen_at,
            "now_playing_id": self.now_playing_id,
            "now_playing_title": self.now_playing_title,
        }


@dataclass
class LanHub:
    """In-memory seeder share state for the current process/session."""

    seeder_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    share_enabled: bool = False
    share_name: str = field(default_factory=default_share_name)
    discovery_port: int = DEFAULT_DISCOVERY_PORT
    # Once the seeder owner approves LAN sharing this browser/process session,
    # remote devices may connect (each device still needs its own approval).
    owner_consented: bool = False
    _sessions: dict[str, LanSession] = field(default_factory=dict)
    _token_index: dict[str, str] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _beacon: DiscoveryBeacon | None = None
    _last_discovered: list[DiscoveredSource] = field(default_factory=list)

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        lan_ip = primary_lan_ip()
        with self._lock:
            beacon = self._beacon
            return {
                "seeder_id": self.seeder_id,
                "share_enabled": self.share_enabled,
                "share_name": self.share_name,
                "owner_consented": self.owner_consented,
                "discovery_port": self.discovery_port,
                "lan_ip": lan_ip,
                "api_port": settings.port,
                "base_url": f"http://{lan_ip}:{settings.port}",
                "beacon_running": bool(beacon and beacon.running),
                "beacon_error": beacon.last_error if beacon else None,
                "hostname": local_hostname(),
                "pending_count": sum(1 for s in self._sessions.values() if s.status == "pending"),
                "active_count": sum(1 for s in self._sessions.values() if s.status == "approved"),
            }

    def set_share(self, *, enabled: bool, name: str | None = None) -> dict[str, Any]:
        with self._lock:
            if name is not None and name.strip():
                self.share_name = name.strip()[:80]
            self.share_enabled = enabled
            if not enabled:
                self.owner_consented = False
                self._revoke_all_locked("Share disabled")
                self._stop_beacon_locked()
            # Beacon starts only after one-time owner consent for this share session.
        return self.status()

    def set_owner_consent(self, approved: bool) -> dict[str, Any]:
        with self._lock:
            if not self.share_enabled:
                return self.status()
            self.owner_consented = bool(approved)
            if not approved:
                self._revoke_all_locked("Owner revoked session consent")
                self._stop_beacon_locked()
            else:
                # Auto-approve any devices that connected while waiting for consent.
                now = _utc_now()
                for session in self._sessions.values():
                    if session.status == "pending":
                        session.status = "approved"
                        session.updated_at = now
                        self._token_index[session.token] = session.session_id
                self._ensure_beacon_locked()
        return self.status()

    def create_session(self, *, device_name: str, device_id: str, client_ip: str) -> LanSession:
        now = _utc_now()
        resolved = resolve_hostname(client_ip)
        clean_name = _display_device_name(device_name, resolved)
        clean_device_id = (device_id or uuid.uuid4().hex).strip()[:80]
        with self._lock:
            if not self.share_enabled:
                raise PermissionError("Sharing is disabled on this seeder")
            # Reuse pending/approved session for same device_id within this share session.
            for existing in self._sessions.values():
                if existing.device_id == clean_device_id and existing.status in {"pending", "approved"}:
                    existing.client_ip = client_ip
                    existing.device_name = clean_name
                    existing.hostname = resolved or existing.hostname
                    existing.updated_at = now
                    existing.last_seen_at = now
                    return existing

            status = "approved" if self.owner_consented else "pending"
            session = LanSession(
                session_id=uuid.uuid4().hex,
                token=secrets.token_urlsafe(24),
                device_name=clean_name,
                device_id=clean_device_id,
                client_ip=client_ip,
                status=status,
                created_at=now,
                updated_at=now,
                last_seen_at=now,
                hostname=resolved,
            )
            self._sessions[session.session_id] = session
            if status == "approved":
                self._token_index[session.token] = session.session_id
            return session

    def get_session(self, session_id: str) -> LanSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def resolve_token(self, token: str | None) -> LanSession | None:
        if not token:
            return None
        with self._lock:
            session_id = self._token_index.get(token)
            if not session_id:
                # Token is known before approval too — look up by token field.
                for session in self._sessions.values():
                    if session.token == token:
                        return session
                return None
            return self._sessions.get(session_id)

    def decide_session(self, session_id: str, *, approve: bool) -> LanSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.status not in {"pending", "approved", "denied"}:
                return session
            now = _utc_now()
            if approve:
                if not self.share_enabled:
                    return session
                self.owner_consented = True
                session.status = "approved"
                self._token_index[session.token] = session.session_id
            else:
                session.status = "denied"
                self._token_index.pop(session.token, None)
            session.updated_at = now
            return session

    def list_devices(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = [
                s
                for s in self._sessions.values()
                if s.status in {"pending", "approved"}
            ]
            sessions.sort(key=lambda s: s.created_at, reverse=True)
            return [s.to_public() for s in sessions]

    def list_pending(self) -> list[dict[str, Any]]:
        with self._lock:
            pending = [s for s in self._sessions.values() if s.status == "pending"]
            pending.sort(key=lambda s: s.created_at)
            return [s.to_public() for s in pending]

    def revoke_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.status = "revoked"
            session.updated_at = _utc_now()
            session.now_playing_id = None
            session.now_playing_title = None
            self._token_index.pop(session.token, None)
            return True

    def touch_session(
        self,
        session: LanSession,
        *,
        media_id: str | None = None,
        media_title: str | None = None,
        clear_playing: bool = False,
    ) -> None:
        with self._lock:
            current = self._sessions.get(session.session_id)
            if current is None or current.status != "approved":
                return
            current.last_seen_at = _utc_now()
            if clear_playing:
                current.now_playing_id = None
                current.now_playing_title = None
            elif media_id is not None:
                current.now_playing_id = media_id
                current.now_playing_title = media_title

    def discover_sources(self) -> list[dict[str, Any]]:
        settings = get_settings()
        found: dict[str, DiscoveredSource] = {
            s.seeder_id: s
            for s in scan_lan_sources(
                discovery_port=self.discovery_port,
                api_port=settings.port,
            )
        }

        # Same machine: scanning from the seeder used to hide ourselves and look "empty".
        with self._lock:
            sharing = self.share_enabled and self.owner_consented
            local_seeder_id = self.seeder_id
            share_name = self.share_name
        lan_ip = primary_lan_ip()
        if sharing:
            found[local_seeder_id] = DiscoveredSource(
                seeder_id=local_seeder_id,
                name=share_name,
                host=lan_ip,
                port=settings.port,
                base_url=f"http://{lan_ip}:{settings.port}",
                is_self=True,
            )

        # Extra HTTP checks for UDP-discovered hosts + this LAN IP.
        candidates = {(s.host, s.port) for s in found.values()}
        candidates.add((lan_ip, settings.port))
        for host, port in candidates:
            verified = probe_http_seeder(host, port)
            if verified is None:
                continue
            existing = found.get(verified.seeder_id)
            found[verified.seeder_id] = DiscoveredSource(
                seeder_id=verified.seeder_id,
                name=verified.name,
                host=verified.host,
                port=verified.port,
                base_url=verified.base_url,
                is_self=bool(existing and existing.is_self)
                or verified.seeder_id == local_seeder_id,
            )

        ordered = sorted(found.values(), key=lambda s: (not s.is_self, s.name.lower()))
        with self._lock:
            self._last_discovered = ordered
        return [s.to_dict() for s in ordered]

    def last_discovered(self) -> list[dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._last_discovered]

    def announce_payload(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.share_enabled or not self.owner_consented:
                return None
            settings = get_settings()
            return {
                "seeder_id": self.seeder_id,
                "name": self.share_name,
                "host": primary_lan_ip(),
                "port": settings.port,
                "share_enabled": True,
            }

    def shutdown(self) -> None:
        with self._lock:
            self.share_enabled = False
            self._revoke_all_locked("Shutdown")
            self._stop_beacon_locked()

    def _ensure_beacon_locked(self) -> None:
        if self._beacon is None:
            self._beacon = DiscoveryBeacon(
                discovery_port=self.discovery_port,
                get_announce=self.announce_payload,
            )
        if not self._beacon.running:
            self._beacon.start()

    def _stop_beacon_locked(self) -> None:
        if self._beacon is not None:
            self._beacon.stop()

    def _revoke_all_locked(self, _reason: str) -> None:
        now = _utc_now()
        for session in self._sessions.values():
            if session.status in {"pending", "approved"}:
                session.status = "revoked"
                session.updated_at = now
                session.now_playing_id = None
                session.now_playing_title = None
        self._token_index.clear()


def _display_device_name(device_name: str, resolved_hostname: str | None) -> str:
    clean = (device_name or "").strip()[:80]
    if clean and clean.lower() not in _GENERIC_DEVICE_NAMES:
        return clean
    if resolved_hostname:
        return resolved_hostname[:80]
    return clean or "Unknown device"


lan_hub = LanHub()
