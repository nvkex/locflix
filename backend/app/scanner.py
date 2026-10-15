from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.ids import media_id_for_path
from app.models import Episode, Movie, Season, Show, VideoFile

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4v"}
POSTER_NAMES = ("poster.jpg", "poster.jpeg", "poster.png", "folder.jpg", "folder.png")
EPISODE_RE = re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,2})", re.IGNORECASE)
# Folder names like "Season 4", "Season 4 Part 1", "S04"
SEASON_FOLDER_RE = re.compile(r"(?:season|series)\s*(?P<season>\d{1,2})\b", re.IGNORECASE)
SEASON_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])S(?P<season>\d{1,2})(?![A-Za-zEe0-9])", re.IGNORECASE)
# Absolute / bare episode numbers: "Show - 60.mkv", "Episode 12", "E12", "Show - 88-91.mkv"
EPISODE_WORD_RE = re.compile(r"\b(?:episode|ep|e)\s*(?P<episode>\d{1,3})\b", re.IGNORECASE)
EPISODE_DASH_RE = re.compile(
    r"\s[-–]\s*(?P<episode>\d{1,3})(?:\s*[-–]\s*\d{1,3})?(?:\s*\.|$)",
    re.IGNORECASE,
)


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
    """Parse classic ``SXXEYY`` tags from a filename."""
    match = EPISODE_RE.search(filename)
    if not match:
        return None
    return int(match.group("season")), int(match.group("episode"))


def infer_season_number(text: str) -> int | None:
    match = SEASON_FOLDER_RE.search(text)
    if match:
        return int(match.group("season"))
    match = SEASON_TOKEN_RE.search(text)
    if match:
        return int(match.group("season"))
    return None


def infer_season_from_path(video: Path, show_root: Path) -> int | None:
    """
    Infer season from nested folders (and optionally the show folder name).

    Examples:
    - ``Show/Season 02/ep.mkv``
    - ``Show/[Group] Show (Season 4 Part 1)/ep.mkv``
    - ``Show (Season 2)/ep.mkv``
    """
    candidates: list[str] = []
    try:
        relative = video.relative_to(show_root)
        candidates.extend(reversed(relative.parts[:-1]))
    except ValueError:
        pass
    candidates.append(show_root.name)
    for part in candidates:
        season = infer_season_number(part)
        if season is not None:
            return season
    return None


def infer_episode_number(filename: str) -> int | None:
    """
    Infer a bare episode number when ``SXXEYY`` is absent.

    Supports ``Show - 60.mkv``, ``Show - 88-91.mkv`` (uses first number),
    ``Episode 12``, ``E12``, ``EP12``.
    """
    stem = Path(filename).stem
    match = EPISODE_WORD_RE.search(stem)
    if match:
        return int(match.group("episode"))
    match = EPISODE_DASH_RE.search(filename if filename.endswith(Path(filename).suffix) else f"{stem}.")
    if match:
        return int(match.group("episode"))
    # Also try against the stem alone with a synthetic extension boundary
    match = EPISODE_DASH_RE.search(f"{stem}.")
    if match:
        return int(match.group("episode"))
    return None


def resolve_episode(video: Path, show_root: Path) -> tuple[int, int] | None:
    """
    Resolve season/episode for a video under a show folder.

    Priority:
    1. ``SXXEYY`` in the filename
    2. Season from parent/show folder name + bare episode number in filename
    """
    tagged = parse_episode(video.name)
    if tagged is not None:
        return tagged

    episode_num = infer_episode_number(video.name)
    if episode_num is None:
        return None

    season_num = infer_season_from_path(video, show_root)
    if season_num is None:
        season_num = 1
    return season_num, episode_num


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
            parsed = resolve_episode(video, child)
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
