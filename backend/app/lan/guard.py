from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.catalog import catalog
from app.lan.hub import lan_hub
from app.lan.netinfo import is_loopback_host

LAN_TOKEN_HEADER = "X-Locflix-Lan-Token"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _is_public_lan_path(path: str, method: str) -> bool:
    if path == "/api/health":
        return True
    if path == "/api/lan/status":
        return True
    if path == "/api/lan/sessions" and method == "POST":
        return True
    if path.startswith("/api/lan/sessions/") and method == "GET":
        return True
    return False


def _is_local_control_path(path: str) -> bool:
    # Seeder UI controls - loopback only.
    return path.startswith("/api/lan/") and not (
        path == "/api/lan/sessions"
        or path.startswith("/api/lan/sessions/")
        or path == "/api/lan/status"
    )


class LanAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()
        client_ip = _client_ip(request)
        loopback = is_loopback_host(client_ip)

        if not path.startswith("/api/"):
            return await call_next(request)

        # Let CORS preflight through.
        if method == "OPTIONS":
            return await call_next(request)

        # Local leecher/seeder control plane always allowed from this machine.
        if loopback:
            response = await call_next(request)
            return response

        if _is_public_lan_path(path, method):
            return await call_next(request)

        if _is_local_control_path(path):
            return JSONResponse({"detail": "LAN control API is local-only"}, status_code=403)

        if not lan_hub.share_enabled:
            return JSONResponse({"detail": "This Locflix seeder is not sharing on the LAN"}, status_code=403)

        token = request.headers.get(LAN_TOKEN_HEADER) or request.query_params.get("lan_token")
        session = lan_hub.resolve_token(token)
        if session is None or session.status != "approved":
            return JSONResponse(
                {"detail": "LAN session not approved. Wait for seeder consent."},
                status_code=403,
            )

        request.state.lan_session = session
        lan_hub.touch_session(session)

        if path.startswith("/api/stream/"):
            media_id = path.rstrip("/").split("/")[-1]
            title = _title_for_media(media_id)
            lan_hub.touch_session(session, media_id=media_id, media_title=title)

        return await call_next(request)


def _title_for_media(media_id: str) -> str | None:
    parent = catalog.get_parent_for_file(media_id)
    if parent is None:
        movie = catalog.get_movie(media_id)
        if movie:
            return movie.title
        show = catalog.get_show(media_id)
        return show.title if show else None
    kind, parent_id = parent
    if kind == "movie":
        movie = catalog.get_movie(parent_id)
        return movie.title if movie else None
    show = catalog.get_show(parent_id)
    if show is None:
        return None
    episode = catalog.get_episode(media_id)
    if episode is None:
        return show.title
    return f"{show.title} · S{episode.season:02d}E{episode.episode:02d}"
