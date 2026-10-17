from __future__ import annotations

import urllib.error
import urllib.request
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.lan.guard import LAN_TOKEN_HEADER
from app.lan.hub import lan_hub
from app.lan.netinfo import default_share_name, is_loopback_host

router = APIRouter(tags=["lan"])


class ShareUpdate(BaseModel):
    enabled: bool
    name: str | None = None


class OwnerConsentUpdate(BaseModel):
    approved: bool


class SessionDecision(BaseModel):
    approve: bool


class CreateSessionBody(BaseModel):
    device_name: str = Field(default="Locflix Leecher", max_length=80)
    device_id: str = Field(default="", max_length=80)


class ConnectBody(BaseModel):
    host: str
    port: int = 8787
    device_name: str = Field(default="Locflix Leecher", max_length=80)
    device_id: str = Field(default="", max_length=80)


def _require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    if not is_loopback_host(host):
        raise HTTPException(status_code=403, detail="Local-only endpoint")


@router.get("/lan/status")
async def lan_status() -> dict[str, Any]:
    return lan_hub.status()


@router.post("/lan/share")
async def update_share(body: ShareUpdate, request: Request) -> dict[str, Any]:
    _require_loopback(request)
    name = body.name if body.name is not None else None
    if body.enabled and not (name or lan_hub.share_name):
        name = default_share_name()
    return lan_hub.set_share(enabled=body.enabled, name=name)


@router.post("/lan/owner-consent")
async def owner_consent(body: OwnerConsentUpdate, request: Request) -> dict[str, Any]:
    """Seeder browser session consent — required once before remotes can stay connected."""
    _require_loopback(request)
    return lan_hub.set_owner_consent(body.approved)


@router.get("/lan/devices")
async def list_devices(request: Request) -> list[dict[str, Any]]:
    _require_loopback(request)
    return lan_hub.list_devices()


@router.get("/lan/consent/pending")
async def pending_consent(request: Request) -> list[dict[str, Any]]:
    _require_loopback(request)
    return lan_hub.list_pending()


@router.post("/lan/consent/{session_id}")
async def decide_consent(session_id: str, body: SessionDecision, request: Request) -> dict[str, Any]:
    _require_loopback(request)
    session = lan_hub.decide_session(session_id, approve=body.approve)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_public()


@router.delete("/lan/devices/{session_id}")
async def revoke_device(session_id: str, request: Request) -> dict[str, str]:
    _require_loopback(request)
    if not lan_hub.revoke_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "revoked"}


@router.post("/lan/discover")
async def discover_sources(request: Request) -> list[dict[str, Any]]:
    _require_loopback(request)
    return lan_hub.discover_sources()


@router.get("/lan/sources")
async def list_sources(request: Request) -> list[dict[str, Any]]:
    _require_loopback(request)
    return lan_hub.last_discovered()


@router.post("/lan/sessions")
async def create_remote_session(body: CreateSessionBody, request: Request) -> dict[str, Any]:
    """Called by leechers (may be remote) to request access."""
    if not lan_hub.share_enabled:
        raise HTTPException(status_code=403, detail="Sharing is disabled")
    client_ip = request.client.host if request.client else ""
    try:
        session = lan_hub.create_session(
            device_name=body.device_name,
            device_id=body.device_id,
            client_ip=client_ip,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "session_id": session.session_id,
        "status": session.status,
        "device_name": session.device_name,
        "share_name": lan_hub.share_name,
        "seeder_id": lan_hub.seeder_id,
        "token": session.token if session.status == "approved" else None,
    }


@router.get("/lan/sessions/{session_id}")
async def get_remote_session(session_id: str) -> dict[str, Any]:
    session = lan_hub.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "status": session.status,
        "device_name": session.device_name,
        "share_name": lan_hub.share_name,
        "seeder_id": lan_hub.seeder_id,
        "token": session.token if session.status == "approved" else None,
    }


@router.post("/lan/connect")
async def connect_to_source(body: ConnectBody, request: Request) -> dict[str, Any]:
    """Leecher helper: ask a discovered seeder for a session (proxied from loopback)."""
    _require_loopback(request)
    host = body.host.strip()
    if not host:
        raise HTTPException(status_code=400, detail="host is required")
    url = f"http://{host}:{int(body.port)}/api/lan/sessions"
    payload = json.dumps(
        {
            "device_name": body.device_name,
            "device_id": body.device_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail or "Seeder rejected connect") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not reach seeder: {exc}") from exc

    return {
        **data,
        "host": host,
        "port": int(body.port),
        "base_url": f"http://{host}:{int(body.port)}",
        "token_header": LAN_TOKEN_HEADER,
    }


@router.get("/lan/connect/{session_id}")
async def poll_connect(session_id: str, request: Request, host: str, port: int = 8787) -> dict[str, Any]:
    _require_loopback(request)
    url = f"http://{host.strip()}:{int(port)}/api/lan/sessions/{session_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail or "Seeder session error") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not reach seeder: {exc}") from exc
    return {
        **data,
        "host": host.strip(),
        "port": int(port),
        "base_url": f"http://{host.strip()}:{int(port)}",
        "token_header": LAN_TOKEN_HEADER,
    }
