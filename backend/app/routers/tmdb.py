from fastapi import APIRouter, HTTPException

from app.catalog import catalog
from app.config import get_settings
from app.models import TmdbInfo
from app.tmdb_info import fetch_tmdb_info, tmdb_configured

router = APIRouter(tags=["tmdb"])


@router.get("/movies/{movie_id}/tmdb", response_model=TmdbInfo)
async def movie_tmdb_info(movie_id: str) -> TmdbInfo:
    settings = get_settings()
    if not tmdb_configured(settings):
        raise HTTPException(status_code=503, detail="TMDB API key not configured")
    movie = catalog.get_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    info = await fetch_tmdb_info(settings, movie.id, movie.title, "movie")
    if info is None:
        raise HTTPException(status_code=404, detail="No TMDB match found")
    return info


@router.get("/series/{show_id}/tmdb", response_model=TmdbInfo)
async def series_tmdb_info(show_id: str) -> TmdbInfo:
    settings = get_settings()
    if not tmdb_configured(settings):
        raise HTTPException(status_code=503, detail="TMDB API key not configured")
    show = catalog.get_show(show_id)
    if show is None:
        raise HTTPException(status_code=404, detail="Series not found")
    info = await fetch_tmdb_info(settings, show.id, show.title, "series")
    if info is None:
        raise HTTPException(status_code=404, detail="No TMDB match found")
    return info
