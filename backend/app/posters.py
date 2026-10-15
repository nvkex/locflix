from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from app.config import Settings
from app.ffmpeg_tools import ffmpeg_path, ffprobe_path
from app.models import Movie, Show
from app.titleparse import parse_title_year

logger = logging.getLogger(__name__)

TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMAGE = "https://image.tmdb.org/t/p/w500"
_TITLE_NORM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", _TITLE_NORM_RE.sub(" ", value.lower())).strip()


def _result_year(result: dict, kind: str) -> int | None:
    date = result.get("release_date") if kind == "movie" else result.get("first_air_date")
    if not date or len(date) < 4 or not date[:4].isdigit():
        return None
    return int(date[:4])


def pick_best_tmdb_result(
    results: list[dict],
    query: str,
    year: int | None,
    kind: str,
    *,
    min_score: float = 0.55,
) -> dict | None:
    """
    Choose the closest title match instead of blindly trusting TMDB rank order.

    Example: query \"Inglourious Bastards\" ranks Indonesian film Merah Putih first,
    while \"Inglourious Basterds\" is the intended 2009 match.
    """
    query_norm = _normalize_title(query)
    if not query_norm or not results:
        return None

    best: dict | None = None
    best_score = -1.0

    for result in results:
        if kind == "movie":
            candidates = [result.get("title") or "", result.get("original_title") or ""]
        else:
            candidates = [result.get("name") or "", result.get("original_name") or ""]

        title_score = 0.0
        for candidate in candidates:
            candidate_norm = _normalize_title(candidate)
            if not candidate_norm:
                continue
            ratio = SequenceMatcher(None, query_norm, candidate_norm).ratio()
            if candidate_norm == query_norm:
                ratio = 1.0
            elif query_norm in candidate_norm or candidate_norm in query_norm:
                ratio = max(ratio, 0.92)
            title_score = max(title_score, ratio)

        score = title_score
        result_year = _result_year(result, kind)
        if year is not None and result_year is not None:
            if result_year == year:
                score += 0.12
            elif abs(result_year - year) == 1:
                score += 0.04
            else:
                score -= 0.08

        if score > best_score:
            best_score = score
            best = result

    if best is None or best_score < min_score:
        return None
    return best


def posters_dir(settings: Settings) -> Path:
    path = settings.data_dir / "posters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def poster_cache_path(settings: Settings, media_id: str) -> Path:
    return posters_dir(settings) / f"{media_id}.jpg"


def poster_api_url(media_id: str) -> str:
    return f"/api/posters/{media_id}"


def _copy_as_jpeg(src: Path, dest: Path) -> bool:
    try:
        suffix = src.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            shutil.copyfile(src, dest)
            return dest.is_file()
        # Let ffmpeg transcode png/webp → jpg when available
        ffmpeg = ffmpeg_path()
        if ffmpeg is None:
            if suffix == ".png":
                shutil.copyfile(src, dest.with_suffix(".png"))
                # Serve path still expects .jpg name — copy bytes anyway for browsers
                shutil.copyfile(src, dest)
                return dest.is_file()
            return False
        result = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-q:v", "2", str(dest)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0 and dest.is_file() and dest.stat().st_size > 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def try_sidecar_poster(folder_or_video: Path, dest: Path) -> bool:
    """
    Look for local artwork next to a movie folder or loose video file.

    - Folder titles: poster.jpg / folder.jpg inside the folder
    - Loose videos: SameName.jpg next to SameName.mkv (and poster.jpg in that folder)
    """
    if folder_or_video.is_file():
        parent = folder_or_video.parent
        stem = folder_or_video.stem
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = parent / f"{stem}{ext}"
            if candidate.is_file() and _copy_as_jpeg(candidate, dest):
                return True
        search_dir = parent
    elif folder_or_video.is_dir():
        search_dir = folder_or_video
    else:
        return False

    for name in ("poster.jpg", "poster.jpeg", "poster.png", "folder.jpg", "folder.png"):
        candidate = search_dir / name
        if candidate.is_file() and _copy_as_jpeg(candidate, dest):
            return True
    return False


def try_embedded_poster(video_path: Path, dest: Path) -> bool:
    probe = ffprobe_path()
    ffmpeg = ffmpeg_path()
    if probe is None or ffmpeg is None or not video_path.is_file():
        return False

    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-select_streams",
                "v",
                "-show_entries",
                "stream=index:stream_disposition=attached_pic",
                "-of",
                "json",
                str(video_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    if result.returncode != 0 or not result.stdout.strip():
        return False

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False

    stream_index = None
    for stream in payload.get("streams") or []:
        disposition = stream.get("disposition") or {}
        if disposition.get("attached_pic") == 1:
            stream_index = stream.get("index")
            break

    if stream_index is None:
        return False

    try:
        extract = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video_path),
                "-map",
                f"0:{stream_index}",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(dest),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    return extract.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def _http_get_json(url: str, timeout: float = 20.0) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Locflix/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("TMDB request failed: %s", exc)
        return None


def _http_download(url: str, dest: Path, timeout: float = 30.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Locflix/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
        return dest.is_file() and dest.stat().st_size > 0
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.warning("Poster download failed: %s", exc)
        return False


def try_tmdb_poster(
    settings: Settings,
    title: str,
    year: int | None,
    kind: str,
    dest: Path,
) -> bool:
    api_key = (settings.tmdb_api_key or "").strip()
    if not api_key:
        return False

    endpoint = "search/movie" if kind == "movie" else "search/tv"
    params = {"api_key": api_key, "query": title, "include_adult": "false"}
    if year is not None:
        if kind == "movie":
            params["year"] = str(year)
        else:
            params["first_air_date_year"] = str(year)

    url = f"{TMDB_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    payload = _http_get_json(url)
    if not payload:
        return False

    results = list(payload.get("results") or [])
    if not results and year is not None:
        # Retry without year if year-constrained search missed
        params.pop("year", None)
        params.pop("first_air_date_year", None)
        url = f"{TMDB_API}/{endpoint}?{urllib.parse.urlencode(params)}"
        payload = _http_get_json(url)
        results = list((payload or {}).get("results") or [])
    if not results:
        return False

    best = pick_best_tmdb_result(results, title, year, kind)
    if best is None:
        logger.info("No close TMDB match for %r (%s, year=%s)", title, kind, year)
        return False

    poster_path = best.get("poster_path")
    if not poster_path:
        return False

    return _http_download(f"{TMDB_IMAGE}{poster_path}", dest)


def resolve_poster_for_title(
    settings: Settings,
    media_id: str,
    folder_name: str,
    folder_path: Path,
    kind: str,
    video_paths: list[Path],
    *,
    force: bool = False,
) -> str | None:
    dest = poster_cache_path(settings, media_id)
    if dest.is_file() and dest.stat().st_size > 0 and not force:
        return poster_api_url(media_id)

    if try_sidecar_poster(folder_path, dest):
        return poster_api_url(media_id)

    # Prefer the largest video for embedded art
    for video in sorted(video_paths, key=lambda p: p.stat().st_size if p.is_file() else 0, reverse=True):
        if try_embedded_poster(video, dest):
            return poster_api_url(media_id)

    clean, year = parse_title_year(folder_name)
    if try_tmdb_poster(settings, clean, year, kind, dest):
        return poster_api_url(media_id)

    return None


def attach_cached_posters(settings: Settings, movies: list[Movie], shows: list[Show]) -> None:
    """Attach already-downloaded posters without network I/O."""
    for movie in movies:
        path = poster_cache_path(settings, movie.id)
        if path.is_file() and path.stat().st_size > 0:
            movie.poster = poster_api_url(movie.id)
    for show in shows:
        path = poster_cache_path(settings, show.id)
        if path.is_file() and path.stat().st_size > 0:
            show.poster = poster_api_url(show.id)


def enrich_movie_posters(settings: Settings, movies: list[Movie], *, force: bool = False) -> int:
    filled = 0
    for movie in movies:
        video_paths = [Path(f.path) for f in movie.files]
        url = resolve_poster_for_title(
            settings,
            movie.id,
            movie.title,
            Path(movie.path),
            "movie",
            video_paths,
            force=force,
        )
        movie.poster = url
        if url:
            filled += 1
    return filled


def enrich_show_posters(settings: Settings, shows: list[Show], *, force: bool = False) -> int:
    filled = 0
    for show in shows:
        video_paths: list[Path] = []
        for season in show.seasons:
            for episode in season.episodes:
                video_paths.append(Path(episode.path))
        url = resolve_poster_for_title(
            settings,
            show.id,
            show.title,
            Path(show.path),
            "series",
            video_paths,
            force=force,
        )
        show.poster = url
        if url:
            filled += 1
    return filled


def enrich_all_posters(settings: Settings, movies: list[Movie], shows: list[Show], *, force: bool = False) -> dict:
    movies_n = enrich_movie_posters(settings, movies, force=force)
    shows_n = enrich_show_posters(settings, shows, force=force)
    return {
        "movies_with_posters": movies_n,
        "series_with_posters": shows_n,
        "tmdb_configured": bool((settings.tmdb_api_key or "").strip()),
    }
