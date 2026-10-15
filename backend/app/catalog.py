from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.media_meta import attach_subtitle_flags, video_has_external_subtitles
from app.models import Episode, Movie, RecentItem, Show
from app.posters import attach_cached_posters, enrich_all_posters
from app.scanner import scan_movies, scan_series


@dataclass
class Catalog:
    movies: list[Movie] = field(default_factory=list)
    shows: list[Show] = field(default_factory=list)
    last_scan_at: str | None = None
    _files_by_id: dict[str, Path] = field(default_factory=dict)
    _movie_by_id: dict[str, Movie] = field(default_factory=dict)
    _show_by_id: dict[str, Show] = field(default_factory=dict)
    _episode_by_id: dict[str, Episode] = field(default_factory=dict)
    _title_by_file_id: dict[str, tuple[str, str]] = field(default_factory=dict)
    _parent_by_file_id: dict[str, tuple[str, str]] = field(default_factory=dict)

    def rebuild_indexes(self) -> None:
        self._files_by_id.clear()
        self._movie_by_id.clear()
        self._show_by_id.clear()
        self._episode_by_id.clear()
        self._title_by_file_id.clear()
        self._parent_by_file_id.clear()

        for movie in self.movies:
            self._movie_by_id[movie.id] = movie
            for vf in movie.files:
                self._files_by_id[vf.id] = Path(vf.path)
                self._title_by_file_id[vf.id] = ("movie_file", movie.title)
                self._parent_by_file_id[vf.id] = ("movie", movie.id)

        for show in self.shows:
            self._show_by_id[show.id] = show
            for season in show.seasons:
                for episode in season.episodes:
                    self._episode_by_id[episode.id] = episode
                    self._files_by_id[episode.id] = Path(episode.path)
                    label = f"{show.title} · S{episode.season:02d}E{episode.episode:02d}"
                    self._title_by_file_id[episode.id] = ("episode", label)
                    self._parent_by_file_id[episode.id] = ("show", show.id)

    def get_movie(self, movie_id: str) -> Movie | None:
        return self._movie_by_id.get(movie_id)

    def get_show(self, show_id: str) -> Show | None:
        return self._show_by_id.get(show_id)

    def get_file_path(self, media_id: str) -> Path | None:
        return self._files_by_id.get(media_id)

    def get_title_meta(self, media_id: str) -> tuple[str, str] | None:
        return self._title_by_file_id.get(media_id)

    def get_poster_for_file(self, media_id: str) -> str | None:
        parent = self._parent_by_file_id.get(media_id)
        if parent is None:
            return None
        kind, parent_id = parent
        if kind == "movie":
            movie = self._movie_by_id.get(parent_id)
            return movie.poster if movie else None
        show = self._show_by_id.get(parent_id)
        return show.poster if show else None

    def get_episode(self, episode_id: str) -> Episode | None:
        return self._episode_by_id.get(episode_id)

    def get_parent_for_file(self, media_id: str) -> tuple[str, str] | None:
        return self._parent_by_file_id.get(media_id)

    def get_has_subtitles_for_file(self, media_id: str) -> bool:
        parent = self._parent_by_file_id.get(media_id)
        if parent is not None:
            kind, parent_id = parent
            if kind == "movie":
                movie = self._movie_by_id.get(parent_id)
                if movie is not None and movie.has_subtitles:
                    return True
            else:
                show = self._show_by_id.get(parent_id)
                if show is not None and show.has_subtitles:
                    return True
        path = self._files_by_id.get(media_id)
        if path is None:
            return False
        return video_has_external_subtitles(path)

    def search(self, query: str) -> dict[str, list]:
        q = query.strip().lower()
        if not q:
            return {"movies": [], "series": []}
        return {
            "movies": [m for m in self.movies if q in m.title.lower()],
            "series": [s for s in self.shows if q in s.title.lower()],
        }

    def recent(self, limit: int = 5) -> list[RecentItem]:
        items: list[RecentItem] = []
        for movie in self.movies:
            if not movie.added_at:
                continue
            items.append(
                RecentItem(
                    id=movie.id,
                    title=movie.title,
                    kind="movie",
                    added_at=movie.added_at,
                    default_file_id=movie.default_file_id,
                    poster=movie.poster,
                    has_subtitles=movie.has_subtitles,
                )
            )
        for show in self.shows:
            if not show.added_at:
                continue
            items.append(
                RecentItem(
                    id=show.id,
                    title=show.title,
                    kind="series",
                    added_at=show.added_at,
                    episode_count=show.episode_count,
                    poster=show.poster,
                    has_subtitles=show.has_subtitles,
                )
            )
        items.sort(key=lambda item: item.added_at, reverse=True)
        return items[: max(0, limit)]



catalog = Catalog()


def rescan(movies_dir: Path, series_dir: Path, *, fetch_posters: bool | None = None) -> Catalog:
    catalog.movies = scan_movies(movies_dir)
    catalog.shows = scan_series(series_dir)
    settings = get_settings()
    # Always wire up posters already on disk (fast).
    attach_cached_posters(settings, catalog.movies, catalog.shows)
    attach_subtitle_flags(catalog.movies, catalog.shows)
    should_fetch = settings.fetch_posters_on_scan if fetch_posters is None else fetch_posters
    if should_fetch:
        enrich_all_posters(settings, catalog.movies, catalog.shows, force=False)
    catalog.last_scan_at = datetime.now(timezone.utc).isoformat()
    catalog.rebuild_indexes()
    return catalog
