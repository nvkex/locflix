from __future__ import annotations

import json
import logging
import urllib.parse
from pathlib import Path

from app import db
from app.config import Settings
from app.models import TmdbInfo
from app.posters import TMDB_API, _http_get_json, pick_best_tmdb_result
from app.titleparse import parse_title_year

logger = logging.getLogger(__name__)


def tmdb_configured(settings: Settings) -> bool:
    return bool((settings.tmdb_api_key or "").strip())


def tmdb_cache_dir(settings: Settings) -> Path:
    """Legacy JSON cache directory (migrated into SQLite on read)."""
    path = settings.data_dir / "tmdb"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tmdb_cache_path(settings: Settings, media_id: str) -> Path:
    return tmdb_cache_dir(settings) / f"{media_id}.json"


def _load_legacy_json_cache(settings: Settings, media_id: str) -> TmdbInfo | None:
    path = tmdb_cache_path(settings, media_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TmdbInfo.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid legacy TMDB cache for %s: %s", media_id, exc)
        return None


def _year_from_date(value: str | None) -> int | None:
    if not value or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _search_best(
    settings: Settings,
    title: str,
    kind: str,
) -> dict | None:
    api_key = (settings.tmdb_api_key or "").strip()
    clean, year = parse_title_year(title)
    endpoint = "search/movie" if kind == "movie" else "search/tv"
    params: dict[str, str] = {
        "api_key": api_key,
        "query": clean or title,
        "include_adult": "false",
    }
    if year is not None:
        if kind == "movie":
            params["year"] = str(year)
        else:
            params["first_air_date_year"] = str(year)

    url = f"{TMDB_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    payload = _http_get_json(url)
    results = list((payload or {}).get("results") or [])
    if not results and year is not None:
        params.pop("year", None)
        params.pop("first_air_date_year", None)
        url = f"{TMDB_API}/{endpoint}?{urllib.parse.urlencode(params)}"
        payload = _http_get_json(url)
        results = list((payload or {}).get("results") or [])
    return pick_best_tmdb_result(results, clean or title, year, kind)


def _fetch_details(settings: Settings, tmdb_id: int, kind: str) -> dict | None:
    api_key = (settings.tmdb_api_key or "").strip()
    endpoint = "movie" if kind == "movie" else "tv"
    params = {
        "api_key": api_key,
        "append_to_response": "credits",
    }
    url = f"{TMDB_API}/{endpoint}/{tmdb_id}?{urllib.parse.urlencode(params)}"
    return _http_get_json(url)


def _directors_from_credits(credits: dict) -> list[str]:
    names: list[str] = []
    for person in credits.get("crew") or []:
        if (person.get("job") or "") == "Director":
            name = (person.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names[:4]


def _cast_from_credits(credits: dict) -> list[str]:
    names: list[str] = []
    for person in credits.get("cast") or []:
        name = (person.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= 5:
            break
    return names


def _runtime_minutes(detail: dict, kind: str) -> int | None:
    if kind == "movie":
        runtime = detail.get("runtime")
        return int(runtime) if isinstance(runtime, int) and runtime > 0 else None
    episode_run = detail.get("episode_run_time") or []
    if isinstance(episode_run, list) and episode_run:
        try:
            return int(episode_run[0])
        except (TypeError, ValueError):
            return None
    return None


def detail_to_info(detail: dict, kind: str) -> TmdbInfo:
    credits = detail.get("credits") or {}
    if kind == "movie":
        title = (detail.get("title") or detail.get("original_title") or "").strip()
        release_date = detail.get("release_date")
        seasons = None
    else:
        title = (detail.get("name") or detail.get("original_name") or "").strip()
        release_date = detail.get("first_air_date")
        seasons_raw = detail.get("number_of_seasons")
        seasons = int(seasons_raw) if isinstance(seasons_raw, int) else None

    genres = [
        str(g.get("name")).strip()
        for g in (detail.get("genres") or [])
        if g.get("name")
    ]
    rating = detail.get("vote_average")
    vote_count = detail.get("vote_count")

    return TmdbInfo(
        tmdb_id=int(detail.get("id") or 0),
        kind=kind,
        title=title or "Untitled",
        overview=(detail.get("overview") or "").strip() or None,
        tagline=(detail.get("tagline") or "").strip() or None,
        rating=float(rating) if isinstance(rating, (int, float)) and rating > 0 else None,
        vote_count=int(vote_count) if isinstance(vote_count, int) else None,
        genres=genres,
        release_year=_year_from_date(release_date),
        release_date=release_date or None,
        runtime_minutes=_runtime_minutes(detail, kind),
        directors=_directors_from_credits(credits),
        cast=_cast_from_credits(credits),
        seasons=seasons,
    )


async def fetch_tmdb_info(
    settings: Settings,
    media_id: str,
    title: str,
    kind: str,
    *,
    force: bool = False,
) -> TmdbInfo | None:
    """Search TMDB and return details. Persisted in SQLite by Locflix media id."""
    if not tmdb_configured(settings):
        return None

    if not force:
        cached = await db.get_tmdb_metadata(media_id)
        if cached is not None:
            return cached

        # One-time migration from older JSON cache files.
        legacy = _load_legacy_json_cache(settings, media_id)
        if legacy is not None:
            await db.upsert_tmdb_metadata(media_id, legacy)
            try:
                tmdb_cache_path(settings, media_id).unlink(missing_ok=True)
            except OSError:
                pass
            return legacy

    match = _search_best(settings, title, kind)
    if match is None or match.get("id") is None:
        return None

    detail = _fetch_details(settings, int(match["id"]), kind)
    if not detail:
        return None

    info = detail_to_info(detail, kind)
    if info.tmdb_id:
        await db.upsert_tmdb_metadata(media_id, info)
    return info
