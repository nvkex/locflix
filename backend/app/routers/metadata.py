from fastapi import APIRouter, HTTPException

from app.catalog import catalog
from app.config import get_settings
from app.media_meta import MediaMetadata, probe_media
from app.models import MediaMetadataResponse
from app.opensubtitles import opensubtitles_configured

router = APIRouter(tags=["metadata"])


@router.get("/media/{media_id}/metadata", response_model=MediaMetadataResponse)
async def get_media_metadata(media_id: str) -> MediaMetadataResponse:
    path = catalog.get_file_path(media_id)
    if path is None:
        # Allow movie/show ids by resolving to a default playable file.
        movie = catalog.get_movie(media_id)
        if movie and movie.default_file_id:
            path = catalog.get_file_path(movie.default_file_id)
            media_id = movie.default_file_id
        else:
            show = catalog.get_show(media_id)
            if show:
                for season in show.seasons:
                    if season.episodes:
                        media_id = season.episodes[0].id
                        path = catalog.get_file_path(media_id)
                        break
    if path is None:
        raise HTTPException(status_code=404, detail="Media not in catalog")

    meta: MediaMetadata = probe_media(media_id, path)
    settings = get_settings()
    subtitles = meta.subtitles if meta.has_subtitles else []
    return MediaMetadataResponse(
        media_id=meta.media_id,
        quality=meta.quality,
        resolution=meta.resolution,
        width=meta.width,
        height=meta.height,
        duration_seconds=meta.duration_seconds,
        duration_label=meta.duration_label,
        container=meta.container,
        video_codec=meta.video_codec,
        video_profile=meta.video_profile,
        frame_rate=meta.frame_rate,
        audio_codec=meta.audio_codec,
        audio_channels=meta.audio_channels,
        sample_rate=meta.sample_rate,
        bitrate_label=meta.bitrate_label,
        size_bytes=meta.size_bytes,
        size_label=meta.size_label,
        subtitles=subtitles,
        audio_languages=meta.audio_languages,
        has_subtitles=meta.has_subtitles,
        can_download_subtitles=opensubtitles_configured(settings) and not meta.has_subtitles,
    )
