from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.catalog import catalog
from app.config import get_settings
from app.ffmpeg_tools import (
    extract_embedded_subtitle_vtt,
    list_embedded_subtitle_streams,
)
from app.models import SubtitleTrack, SubtitlesResponse
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

    return SubtitlesResponse(
        media_id=media_id,
        tracks=tracks,
        embedded_possible=True,
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
