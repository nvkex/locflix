from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app import db
from app.catalog import catalog
from app.config import get_settings
from app.ffmpeg_tools import (
    extract_embedded_subtitle_vtt,
    list_embedded_subtitle_streams,
)
from app.media_meta import video_has_subtitles
from app.models import SubtitleDownloadResponse, SubtitleTrack, SubtitlesResponse
from app.opensubtitles import (
    build_search_context_for_media,
    download_english_srt,
    opensubtitles_configured,
)
from app.pathsafety import is_under_roots
from app.subtitles import ExternalSubtitle, find_external_subtitles, load_as_vtt

router = APIRouter(tags=["subtitles"])


def _roots() -> list[Path]:
    settings = get_settings()
    return [settings.movies_dir, settings.series_dir]


def _video_path(media_id: str) -> Path:
    path = catalog.get_file_path(media_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    if not is_under_roots(path, _roots()):
        raise HTTPException(status_code=403, detail="Path not allowed")
    return path


def _external_for_media(media_id: str) -> list[ExternalSubtitle]:
    path = _video_path(media_id)
    allowed: list[ExternalSubtitle] = []
    for ext in find_external_subtitles(path):
        if is_under_roots(ext.path, _roots()):
            allowed.append(ext)
    return allowed


def _mark_parent_has_subtitles(media_id: str) -> None:
    parent = catalog.get_parent_for_file(media_id)
    if parent is None:
        return
    kind, parent_id = parent
    if kind == "movie":
        movie = catalog.get_movie(parent_id)
        if movie is not None:
            movie.has_subtitles = True
    else:
        show = catalog.get_show(parent_id)
        if show is not None:
            show.has_subtitles = True


@router.get("/media/{media_id}/subtitles", response_model=SubtitlesResponse)
async def list_subtitles(media_id: str) -> SubtitlesResponse:
    path = _video_path(media_id)
    tracks: list[SubtitleTrack] = []

    for ext in _external_for_media(media_id):
        tracks.append(
            SubtitleTrack(
                id=ext.track_id,
                label=ext.label,
                language=ext.language,
                source="external",
                format=ext.format,
            )
        )

    for i, emb in enumerate(list_embedded_subtitle_streams(path)):
        tracks.append(
            SubtitleTrack(
                id=f"emb-{i}",
                label=emb.label,
                language=emb.language,
                source="embedded",
                format=emb.codec_name,
            )
        )

    pref = await db.get_subtitle_pref(media_id)
    return SubtitlesResponse(
        media_id=media_id,
        tracks=tracks,
        embedded_possible=True,
        preferred_language=pref["preferred_language"] if pref else None,
    )


@router.post("/media/{media_id}/subtitles/download", response_model=SubtitleDownloadResponse)
async def download_english_subtitles(media_id: str) -> SubtitleDownloadResponse:
    """Download English subtitles from OpenSubtitles when none are present."""
    settings = get_settings()
    if not opensubtitles_configured(settings):
        raise HTTPException(
            status_code=503,
            detail="Set LOCFLIX_OPENSUBTITLES_API_KEY to download subtitles",
        )

    path = _video_path(media_id)
    if video_has_subtitles(path, probe_embedded=True):
        raise HTTPException(
            status_code=409,
            detail="Subtitles already available for this media",
        )

    parent = catalog.get_parent_for_file(media_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Media not in catalog")

    kind, parent_id = parent
    if kind == "movie":
        movie = catalog.get_movie(parent_id)
        if movie is None:
            raise HTTPException(status_code=404, detail="Movie not found")
        ctx = build_search_context_for_media(
            title=movie.title,
            kind="movie",
            video_path=path,
        )
    else:
        show = catalog.get_show(parent_id)
        episode = catalog.get_episode(media_id)
        if show is None or episode is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        ctx = build_search_context_for_media(
            title=show.title,
            kind="episode",
            video_path=path,
            season=episode.season,
            episode=episode.episode,
        )

    dest = path.with_name(f"{path.stem}.en.srt")
    try:
        downloaded = download_english_srt(settings, ctx, dest)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    updated_at = datetime.now(timezone.utc).isoformat()
    await db.upsert_subtitle_pref(media_id, "en", updated_at)
    _mark_parent_has_subtitles(media_id)

    return SubtitleDownloadResponse(
        media_id=media_id,
        path=str(downloaded.path),
        language="en",
        label="ENG",
        preferred_language="en",
        has_subtitles=True,
    )


@router.get("/media/{media_id}/subtitles/{track_id}")
async def get_subtitle_vtt(media_id: str, track_id: str) -> PlainTextResponse:
    # External sidecars
    if track_id.startswith("ext-"):
        for ext in _external_for_media(media_id):
            if ext.track_id != track_id:
                continue
            try:
                vtt = load_as_vtt(ext.path)
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Failed to read subtitle: {exc}") from exc
            except ValueError as exc:
                raise HTTPException(status_code=415, detail=str(exc)) from exc
            return PlainTextResponse(vtt, media_type="text/vtt; charset=utf-8")
        raise HTTPException(status_code=404, detail="Subtitle track not found")

    # Embedded streams extracted via ffmpeg on demand (cached)
    if track_id.startswith("emb-"):
        try:
            emb_index = int(track_id.split("-", 1)[1])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Subtitle track not found") from exc

        path = _video_path(media_id)
        embedded = list_embedded_subtitle_streams(path)
        if emb_index < 0 or emb_index >= len(embedded):
            raise HTTPException(status_code=404, detail="Subtitle track not found")

        stream = embedded[emb_index]
        settings = get_settings()
        cache_path = settings.data_dir / "subs" / f"{media_id}_{track_id}.vtt"
        try:
            if not cache_path.is_file() or cache_path.stat().st_mtime < path.stat().st_mtime:
                extract_embedded_subtitle_vtt(path, stream.stream_index, cache_path)
            vtt = cache_path.read_text(encoding="utf-8", errors="replace")
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to extract subtitles: {exc}") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read extracted subtitles: {exc}") from exc

        return PlainTextResponse(vtt, media_type="text/vtt; charset=utf-8")

    raise HTTPException(status_code=404, detail="Subtitle track not found")
