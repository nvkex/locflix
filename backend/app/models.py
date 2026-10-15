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
    has_subtitles: bool = False


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
    has_subtitles: bool = False


class RecentItem(BaseModel):
    id: str
    title: str
    kind: str  # movie | series
    added_at: str
    episode_count: int | None = None
    default_file_id: str | None = None
    poster: str | None = None
    has_subtitles: bool = False


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
    poster: str | None = None
    has_subtitles: bool = False


class ProgressUpdate(BaseModel):
    position_seconds: float
    duration_seconds: float | None = None


class MediaMetadataResponse(BaseModel):
    media_id: str
    quality: str | None = None
    resolution: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    duration_label: str | None = None
    container: str | None = None
    video_codec: str | None = None
    video_profile: str | None = None
    frame_rate: str | None = None
    audio_codec: str | None = None
    audio_channels: str | None = None
    sample_rate: str | None = None
    bitrate_label: str | None = None
    size_bytes: int | None = None
    size_label: str | None = None
    subtitles: list[str] = Field(default_factory=list)
    audio_languages: list[str] = Field(default_factory=list)
    has_subtitles: bool = False
    can_download_subtitles: bool = False


class SubtitleDownloadResponse(BaseModel):
    media_id: str
    path: str
    language: str = "en"
    label: str = "ENG"
    preferred_language: str = "en"
    has_subtitles: bool = True


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
    preferred_language: str | None = None
