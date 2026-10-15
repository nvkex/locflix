from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.ffmpeg_tools import ffprobe_path, list_embedded_subtitle_streams
from app.models import Movie, Show
from app.subtitles import find_external_subtitles

logger = logging.getLogger(__name__)

_probe_cache: dict[tuple[str, int, int], dict] = {}


@dataclass
class MediaMetadata:
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
    subtitles: list[str] = field(default_factory=list)
    audio_languages: list[str] = field(default_factory=list)
    has_subtitles: bool = False


def quality_from_height(height: int | None) -> str | None:
    """Map pixel height to a standard label (tolerant of slight crop, e.g. 1078 → 1080p)."""
    if height is None or height <= 0:
        return None
    if height >= 2100:
        return "2160p"
    if height >= 1400:
        return "1440p"
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    if height >= 460:
        return "480p"
    return f"{height}p"


def format_duration(seconds: float | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_size(num_bytes: int | None) -> str | None:
    if num_bytes is None or num_bytes <= 0:
        return None
    if num_bytes < 1024**2:
        return f"{num_bytes / 1024:.0f} KB"
    if num_bytes < 1024**3:
        return f"{num_bytes / 1024**2:.1f} MB"
    return f"{num_bytes / 1024**3:.2f} GB"


def format_bitrate(bits_per_second: int | float | None) -> str | None:
    if bits_per_second is None:
        return None
    try:
        bps = float(bits_per_second)
    except (TypeError, ValueError):
        return None
    if bps <= 0:
        return None
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} Mbps"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} kbps"
    return f"{int(bps)} bps"


def format_frame_rate(raw: str | None) -> str | None:
    if not raw or raw in {"0/0", "N/A"}:
        return None
    if "/" in raw:
        num_s, den_s = raw.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
        except ValueError:
            return None
        if den == 0:
            return None
        fps = num / den
    else:
        try:
            fps = float(raw)
        except ValueError:
            return None
    if fps <= 0:
        return None
    if abs(fps - round(fps)) < 0.02:
        return f"{int(round(fps))} fps"
    return f"{fps:.3f}".rstrip("0").rstrip(".") + " fps"


def format_codec(name: str | None) -> str | None:
    if not name:
        return None
    mapping = {
        "h264": "H.264",
        "hevc": "H.265",
        "h265": "H.265",
        "av1": "AV1",
        "vp9": "VP9",
        "vp8": "VP8",
        "mpeg4": "MPEG-4",
        "mpeg2video": "MPEG-2",
        "aac": "AAC",
        "mp3": "MP3",
        "ac3": "AC3",
        "eac3": "E-AC3",
        "dts": "DTS",
        "truehd": "TrueHD",
        "opus": "Opus",
        "flac": "FLAC",
        "pcm_s16le": "PCM",
    }
    return mapping.get(name.lower(), name.upper())


def format_container(format_name: str | None) -> str | None:
    if not format_name:
        return None
    primary = format_name.split(",")[0].strip().lower()
    mapping = {
        "matroska": "MKV",
        "mov": "MP4",
        "mp4": "MP4",
        "avi": "AVI",
        "webm": "WebM",
        "mpegts": "TS",
        "mpeg": "MPEG",
    }
    return mapping.get(primary, primary.upper())


def format_channels(channels: int | None, layout: str | None) -> str | None:
    if layout:
        pretty = {
            "mono": "Mono",
            "stereo": "Stereo",
            "5.1": "5.1",
            "5.1(side)": "5.1",
            "7.1": "7.1",
        }
        return pretty.get(layout.lower(), layout)
    if channels == 1:
        return "Mono"
    if channels == 2:
        return "Stereo"
    if channels and channels > 0:
        return f"{channels} ch"
    return None


def format_sample_rate(rate: str | int | None) -> str | None:
    if rate is None:
        return None
    try:
        value = int(float(rate))
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value >= 1000:
        khz = value / 1000
        if abs(khz - round(khz)) < 0.05:
            return f"{int(round(khz))} kHz"
        return f"{khz:.1f} kHz"
    return f"{value} Hz"


def _display_lang(raw: str | None, *, fallback: str | None = None) -> str | None:
    if raw:
        value = raw.strip()
        if value and value.lower() not in {"und", "unknown", "null"}:
            if len(value) <= 3 and value.isalpha():
                return value.upper()
            return value
    return fallback


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _ffprobe_payload(video_path: Path) -> dict:
    probe = ffprobe_path()
    if probe is None or not video_path.is_file():
        return {}

    try:
        stat = video_path.stat()
        cache_key = (str(video_path.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}

    cached = _probe_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration,bit_rate,size:"
                "stream=index,codec_type,codec_name,profile,width,height,"
                "avg_frame_rate,r_frame_rate,bit_rate,channels,channel_layout,sample_rate:"
                "stream_tags=language,title",
                "-of",
                "json",
                str(video_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffprobe failed for %s: %s", video_path, exc)
        return {}

    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    _probe_cache[cache_key] = payload
    if len(_probe_cache) > 512:
        _probe_cache.clear()
        _probe_cache[cache_key] = payload
    return payload


def external_subtitle_labels(video_path: Path) -> list[str]:
    labels: list[str] = []
    for track in find_external_subtitles(video_path):
        label = track.label.strip() if track.label else ""
        if not label or label.casefold() == "subtitles":
            label = _display_lang(track.language, fallback=track.path.stem) or track.path.name
        labels.append(label)
    return _unique_preserve(labels)


def video_has_external_subtitles(video_path: Path) -> bool:
    return bool(find_external_subtitles(video_path))


def video_has_subtitles(video_path: Path, *, probe_embedded: bool = True) -> bool:
    if video_has_external_subtitles(video_path):
        return True
    if not probe_embedded:
        return False
    return bool(list_embedded_subtitle_streams(video_path))


def paths_have_subtitles(video_paths: list[Path], *, max_embedded_probes: int = 1) -> bool:
    """True if any path has external subs, else probe up to N files for embedded tracks."""
    existing = [path for path in video_paths if path.is_file()]
    if not existing:
        return False
    for path in existing:
        if video_has_external_subtitles(path):
            return True
    probes = 0
    for path in sorted(existing, key=lambda p: p.stat().st_size if p.is_file() else 0, reverse=True):
        if probes >= max_embedded_probes:
            break
        probes += 1
        if list_embedded_subtitle_streams(path):
            return True
    return False


def probe_media(media_id: str, video_path: Path) -> MediaMetadata:
    meta = MediaMetadata(media_id=media_id)
    if not video_path.is_file():
        return meta

    payload = _ffprobe_payload(video_path)
    fmt = payload.get("format") or {}
    streams = list(payload.get("streams") or [])

    subtitles = external_subtitle_labels(video_path)
    audio: list[str] = []
    width: int | None = None
    height: int | None = None
    saw_embedded_subs = False
    video_codec: str | None = None
    video_profile: str | None = None
    frame_rate: str | None = None
    audio_codec: str | None = None
    audio_channels: str | None = None
    sample_rate: str | None = None

    for stream in streams:
        codec_type = (stream.get("codec_type") or "").lower()
        tags = stream.get("tags") or {}
        if codec_type == "video" and width is None:
            w = stream.get("width")
            h = stream.get("height")
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                width, height = w, h
            video_codec = format_codec(stream.get("codec_name"))
            profile = stream.get("profile")
            video_profile = str(profile) if profile else None
            frame_rate = format_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
        elif codec_type == "audio":
            label = _display_lang(tags.get("language"), fallback=_display_lang(tags.get("title")))
            if label:
                audio.append(label)
            else:
                audio.append(f"Track {len(audio) + 1}")
            if audio_codec is None:
                audio_codec = format_codec(stream.get("codec_name"))
                channels = stream.get("channels")
                audio_channels = format_channels(
                    int(channels) if isinstance(channels, int) else None,
                    stream.get("channel_layout"),
                )
                sample_rate = format_sample_rate(stream.get("sample_rate"))
        elif codec_type == "subtitle":
            saw_embedded_subs = True
            label = _display_lang(
                tags.get("language"),
                fallback=_display_lang(tags.get("title"), fallback="Embedded"),
            )
            if label:
                subtitles.append(label)

    if not saw_embedded_subs:
        for emb in list_embedded_subtitle_streams(video_path):
            subtitles.append(emb.label)

    duration: float | None = None
    raw_duration = fmt.get("duration")
    if raw_duration is not None:
        try:
            duration = float(raw_duration)
        except (TypeError, ValueError):
            duration = None

    size_bytes: int | None = None
    raw_size = fmt.get("size")
    if raw_size is not None:
        try:
            size_bytes = int(raw_size)
        except (TypeError, ValueError):
            size_bytes = None
    if size_bytes is None:
        try:
            size_bytes = video_path.stat().st_size
        except OSError:
            size_bytes = None

    bitrate = None
    raw_bitrate = fmt.get("bit_rate")
    if raw_bitrate is not None:
        try:
            bitrate = float(raw_bitrate)
        except (TypeError, ValueError):
            bitrate = None

    meta.width = width
    meta.height = height
    meta.quality = quality_from_height(height)
    meta.resolution = f"{width}×{height}" if width and height else None
    meta.duration_seconds = duration
    meta.duration_label = format_duration(duration)
    meta.container = format_container(fmt.get("format_name"))
    meta.video_codec = video_codec
    meta.video_profile = video_profile
    meta.frame_rate = frame_rate
    meta.audio_codec = audio_codec
    meta.audio_channels = audio_channels
    meta.sample_rate = sample_rate
    meta.bitrate_label = format_bitrate(bitrate)
    meta.size_bytes = size_bytes
    meta.size_label = format_size(size_bytes)
    meta.subtitles = _unique_preserve(subtitles)
    meta.audio_languages = _unique_preserve(audio)
    meta.has_subtitles = bool(meta.subtitles)
    return meta


def attach_subtitle_flags(movies: list[Movie], shows: list[Show]) -> None:
    """Set has_subtitles on catalog titles (external first, limited embedded probes)."""
    for movie in movies:
        paths = [Path(f.path) for f in movie.files]
        movie.has_subtitles = paths_have_subtitles(paths, max_embedded_probes=1)
    for show in shows:
        paths = [Path(ep.path) for season in show.seasons for ep in season.episodes]
        show.has_subtitles = paths_have_subtitles(paths, max_embedded_probes=1)
