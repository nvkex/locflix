from fastapi import APIRouter, HTTPException, Query

from app.catalog import catalog, rescan
from app.config import get_settings
from app.models import LibrarySummary, Movie, RecentItem, Show

router = APIRouter(tags=["library"])


@router.get("/library", response_model=LibrarySummary)
async def library_summary() -> LibrarySummary:
    settings = get_settings()
    return LibrarySummary(
        movies=len(catalog.movies),
        series=len(catalog.shows),
        episodes=sum(s.episode_count for s in catalog.shows),
        last_scan_at=catalog.last_scan_at,
        movies_dir=str(settings.movies_dir),
        series_dir=str(settings.series_dir),
    )


@router.get("/movies", response_model=list[Movie])
async def list_movies() -> list[Movie]:
    return catalog.movies


@router.get("/movies/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str) -> Movie:
    movie = catalog.get_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.get("/series", response_model=list[Show])
async def list_series() -> list[Show]:
    return catalog.shows


@router.get("/series/{show_id}", response_model=Show)
async def get_series(show_id: str) -> Show:
    show = catalog.get_show(show_id)
    if show is None:
        raise HTTPException(status_code=404, detail="Series not found")
    return show


@router.get("/search")
async def search(q: str = Query(default="", min_length=0)) -> dict:
    return catalog.search(q)


@router.get("/recent", response_model=list[RecentItem])
async def list_recent(limit: int = Query(default=5, ge=1, le=20)) -> list[RecentItem]:
    """Latest titles by filesystem created/birth time (mtime fallback)."""
    return catalog.recent(limit=limit)


@router.post("/scan", response_model=LibrarySummary)
async def trigger_scan() -> LibrarySummary:
    settings = get_settings()
    rescan(settings.movies_dir, settings.series_dir)
    return await library_summary()
