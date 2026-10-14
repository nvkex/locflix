from pydantic import BaseModel, Field


class VideoFile(BaseModel):
    id: str
    filename: str
    path: str
    size: int = 0


class Movie(BaseModel):
    id: str
    title: str
    path: str
    poster: str | None = None
    files: list[VideoFile] = Field(default_factory=list)
    default_file_id: str | None = None
    added_at: str | None = None


class Episode(BaseModel):
    id: str
    season: int
    episode: int
    title: str | None = None
    filename: str
    path: str
    size: int = 0


class Season(BaseModel):
    number: int
    episodes: list[Episode] = Field(default_factory=list)


class Show(BaseModel):
    id: str
    title: str
    path: str
    poster: str | None = None
    seasons: list[Season] = Field(default_factory=list)
    episode_count: int = 0
    added_at: str | None = None


class RecentItem(BaseModel):
    id: str
    title: str
    kind: str  # movie | series
    added_at: str
    episode_count: int | None = None
    default_file_id: str | None = None
    poster: str | None = None


class LibrarySummary(BaseModel):
    movies: int
    series: int
    episodes: int
    last_scan_at: str | None = None
    movies_dir: str
    series_dir: str


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ProgressEntry(BaseModel):
    media_id: str
    position_seconds: float
    duration_seconds: float | None = None
    updated_at: str
    title: str | None = None
    kind: str | None = None  # movie_file | episode


class ProgressUpdate(BaseModel):
    position_seconds: float
    duration_seconds: float | None = None


class SubtitleTrack(BaseModel):
    id: str
    label: str
    language: str | None = None
    source: str  # external | embedded
    format: str | None = None


class SubtitlesResponse(BaseModel):
    media_id: str
    tracks: list[SubtitleTrack] = Field(default_factory=list)
    embedded_possible: bool = True
