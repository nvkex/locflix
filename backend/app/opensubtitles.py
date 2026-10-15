from __future__ import annotations

import json
import logging
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.titleparse import parse_title_year

logger = logging.getLogger(__name__)

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "Locflix v0.1.0"


@dataclass(frozen=True)
class SubtitleSearchContext:
    query: str
    year: int | None
    kind: str  # movie | episode
    season: int | None = None
    episode: int | None = None
    video_path: Path | None = None


@dataclass(frozen=True)
class DownloadedSubtitle:
    path: Path
    language: str
    release: str | None


def opensubtitles_configured(settings: Settings) -> bool:
    return bool((settings.opensubtitles_api_key or "").strip())


def movie_hash(path: Path) -> str | None:
    """OpenSubtitles movie hash (size + first/last 64 KiB)."""
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size < 65536 * 2:
        return None

    hash_value = size
    try:
        with path.open("rb") as handle:
            hash_value += sum(struct.unpack("<Q", handle.read(8))[0] for _ in range(8192))
            handle.seek(max(0, size - 65536))
            hash_value += sum(struct.unpack("<Q", handle.read(8))[0] for _ in range(8192))
    except OSError:
        return None
    return f"{hash_value & 0xFFFFFFFFFFFFFFFF:016x}"


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Api-Key": (settings.opensubtitles_api_key or "").strip(),
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _http_json(
    url: str,
    *,
    settings: Settings,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 30.0,
) -> dict | None:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(settings), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.warning("OpenSubtitles %s %s failed: %s %s", method, url, exc.code, detail[:300])
        raise RuntimeError(f"OpenSubtitles error {exc.code}: {detail[:200]}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("OpenSubtitles request failed: %s", exc)
        raise RuntimeError(f"OpenSubtitles request failed: {exc}") from exc


def _http_download_bytes(url: str, timeout: float = 45.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Failed to download subtitle file: {exc}") from exc


def search_english_subtitle(settings: Settings, ctx: SubtitleSearchContext) -> dict | None:
    if not opensubtitles_configured(settings):
        raise RuntimeError("OpenSubtitles API key not configured")

    params: dict[str, str] = {
        "languages": "en",
        "order_by": "download_count",
        "order_direction": "desc",
    }
    if ctx.kind == "episode":
        params["type"] = "episode"
        if ctx.season is not None:
            params["season_number"] = str(ctx.season)
        if ctx.episode is not None:
            params["episode_number"] = str(ctx.episode)
    else:
        params["type"] = "movie"

    if ctx.query:
        params["query"] = ctx.query
    if ctx.year is not None:
        params["year"] = str(ctx.year)
    if ctx.video_path is not None:
        digest = movie_hash(ctx.video_path)
        if digest:
            params["moviehash"] = digest

    url = f"{API_BASE}/subtitles?{urllib.parse.urlencode(params)}"
    payload = _http_json(url, settings=settings)
    results = list((payload or {}).get("data") or [])
    if not results and "moviehash" in params:
        # Retry without hash if hash search missed
        params.pop("moviehash", None)
        url = f"{API_BASE}/subtitles?{urllib.parse.urlencode(params)}"
        payload = _http_json(url, settings=settings)
        results = list((payload or {}).get("data") or [])
    if not results:
        return None

    # Prefer exact language English and a usable file_id
    for item in results:
        attrs = item.get("attributes") or {}
        files = attrs.get("files") or []
        if not files:
            continue
        lang = (attrs.get("language") or "").lower()
        if lang and lang not in {"en", "eng"}:
            continue
        return item
    return results[0]


def download_english_srt(settings: Settings, ctx: SubtitleSearchContext, dest: Path) -> DownloadedSubtitle:
    match = search_english_subtitle(settings, ctx)
    if match is None:
        raise RuntimeError("No English subtitles found on OpenSubtitles")

    attrs = match.get("attributes") or {}
    files = attrs.get("files") or []
    if not files:
        raise RuntimeError("Subtitle result had no downloadable files")
    file_id = files[0].get("file_id")
    if file_id is None:
        raise RuntimeError("Subtitle result missing file_id")

    download_payload = _http_json(
        f"{API_BASE}/download",
        settings=settings,
        method="POST",
        body={"file_id": int(file_id)},
    )
    link = (download_payload or {}).get("link")
    if not link:
        raise RuntimeError("OpenSubtitles did not return a download link")

    content = _http_download_bytes(link)
    # OpenSubtitles may return gzip for some links; urllib usually decompresses.
    text = content.decode("utf-8", errors="replace")
    if not text.strip():
        raise RuntimeError("Downloaded subtitle file was empty")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError("Failed to write subtitle file")

    return DownloadedSubtitle(
        path=dest,
        language="en",
        release=attrs.get("release"),
    )


def build_search_context_for_media(
    *,
    title: str,
    kind: str,
    video_path: Path,
    season: int | None = None,
    episode: int | None = None,
) -> SubtitleSearchContext:
    clean, year = parse_title_year(title)
    return SubtitleSearchContext(
        query=clean or title,
        year=year,
        kind=kind,
        season=season,
        episode=episode,
        video_path=video_path,
    )
