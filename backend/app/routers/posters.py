from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.catalog import catalog, rescan
from app.config import get_settings
from app.posters import enrich_all_posters, poster_cache_path

router = APIRouter(tags=["posters"])


@router.get("/posters/{media_id}")
async def get_poster(media_id: str) -> FileResponse:
    settings = get_settings()
    path = poster_cache_path(settings, media_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Poster not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


@router.post("/posters/fetch")
async def fetch_posters(force: bool = False) -> dict:
    """Download/extract missing posters (uses TMDB when LOCFLIX_TMDB_API_KEY is set)."""
    settings = get_settings()
    if not catalog.movies and not catalog.shows:
        rescan(settings.movies_dir, settings.series_dir, fetch_posters=False)
    result = enrich_all_posters(settings, catalog.movies, catalog.shows, force=force)
    catalog.rebuild_indexes()
    return result
