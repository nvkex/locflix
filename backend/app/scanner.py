from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.ids import media_id_for_path
from app.models import Episode, Movie, Season, Show, VideoFile

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4v"}
POSTER_NAMES = ("poster.jpg", "poster.jpeg", "poster.png", "folder.jpg", "folder.png")
EPISODE_RE = re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,2})", re.IGNORECASE)


def is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def path_created_timestamp(path: Path) -> float:
    """
    Best-effort filesystem "added/created" time.

    - Prefers st_birthtime when the OS exposes it (macOS, some BSDs, newer Python/Windows)
    - On Windows, st_ctime is the creation time
    - Falls back to st_mtime (last modified) when birth/creation isn't available
    """
    try:
        stat = path.stat()
    except OSError:
        return 0.0

    birth = getattr(stat, "st_birthtime", None)
    if birth is not None:
        return float(birth)
    return float(stat.st_ctime)


def title_added_at(folder: Path, video_paths: list[Path]) -> str:
    """When the title most recently appeared/grew in the library."""
    times = [path_created_timestamp(folder)]
    for video in video_paths:
        times.append(path_created_timestamp(video))
    ts = max(times) if times else 0.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def find_poster(folder: Path) -> str | None:
    for name in POSTER_NAMES:
        candidate = folder / name
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def iter_videos(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    videos: list[Path] = []
    for path in folder.rglob("*"):
        if is_video(path):
            videos.append(path)
    return sorted(videos, key=lambda p: p.name.lower())


def pick_default_file(files: list[VideoFile]) -> str | None:
    if not files:
        return None
    return max(files, key=lambda f: f.size).id


def _movie_from_folder(folder: Path) -> Movie | None:
    video_paths = iter_videos(folder)
    files: list[VideoFile] = []
    for video in video_paths:
        files.append(
            VideoFile(
                id=media_id_for_path(video),
                filename=video.name,
                path=str(video.resolve()),
                size=video.stat().st_size,
            )
        )

    if not files:
        return None

    return Movie(
        id=media_id_for_path(folder),
        title=folder.name,
        path=str(folder.resolve()),
        poster=None,  # filled by poster enrichment / cache
        files=files,
        default_file_id=pick_default_file(files),
        added_at=title_added_at(folder, video_paths),
    )


def _movie_from_loose_video(video: Path) -> Movie | None:
    try:
        size = video.stat().st_size
    except OSError:
        return None

    file = VideoFile(
        id=media_id_for_path(video),
        filename=video.name,
        path=str(video.resolve()),
        size=size,
    )
    return Movie(
        id=media_id_for_path(video),
        title=video.stem,
        path=str(video.resolve()),
        poster=None,  # filled by poster enrichment / cache
        files=[file],
        default_file_id=file.id,
        added_at=title_added_at(video, [video]),
    )


def scan_movies(movies_dir: Path) -> list[Movie]:
    """
    Catalog movies from:
    - each subfolder (all videos inside = one title)
    - loose video files directly under the Movies root (.mp4, .mkv, etc.)
    """
    if not movies_dir.is_dir():
        return []

    movies: list[Movie] = []
    try:
        children = sorted(movies_dir.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []

    for child in children:
        try:
            if child.is_dir():
                movie = _movie_from_folder(child)
                if movie is not None:
                    movies.append(movie)
            elif is_video(child):
                loose = _movie_from_loose_video(child)
                if loose is not None:
                    movies.append(loose)
        except OSError:
            # Skip unreadable entries instead of failing the whole library scan
            continue

    return movies


def parse_episode(filename: str) -> tuple[int, int] | None:
    match = EPISODE_RE.search(filename)
    if not match:
        return None
    return int(match.group("season")), int(match.group("episode"))


def scan_series(series_dir: Path) -> list[Show]:
    if not series_dir.is_dir():
        return []

    shows: list[Show] = []
    for child in sorted(series_dir.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue

        by_season: dict[int, list[Episode]] = {}
        matched_videos: list[Path] = []
        for video in iter_videos(child):
            parsed = parse_episode(video.name)
            if parsed is None:
                continue
            matched_videos.append(video)
            season_num, episode_num = parsed
            episode = Episode(
                id=media_id_for_path(video),
                season=season_num,
                episode=episode_num,
                title=None,
                filename=video.name,
                path=str(video.resolve()),
                size=video.stat().st_size,
            )
            by_season.setdefault(season_num, []).append(episode)

        if not by_season:
            continue

        seasons: list[Season] = []
        episode_count = 0
        for season_num in sorted(by_season):
            episodes = sorted(
                by_season[season_num],
                key=lambda e: (e.episode, e.filename.lower()),
            )
            episode_count += len(episodes)
            seasons.append(Season(number=season_num, episodes=episodes))

        shows.append(
            Show(
                id=media_id_for_path(child),
                title=child.name,
                path=str(child.resolve()),
                poster=None,  # filled by poster enrichment / cache
                seasons=seasons,
                episode_count=episode_count,
                added_at=title_added_at(child, matched_videos),
            )
        )

    return shows
