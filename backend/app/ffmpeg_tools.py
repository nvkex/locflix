from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _resolve_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    # Common Windows install locations (winget / Gyan builds)
    candidates = [
        Path(r"C:\Program Files\ffmpeg\bin") / f"{name}.exe",
        Path(r"C:\ffmpeg\bin") / f"{name}.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def ffmpeg_path() -> str | None:
    return _resolve_bin("ffmpeg")


def ffprobe_path() -> str | None:
    return _resolve_bin("ffprobe")


@dataclass(frozen=True)
class EmbeddedSubtitleStream:
    stream_index: int
    codec_name: str | None
    language: str | None
    title: str | None

    @property
    def label(self) -> str:
        if self.language:
            return self.language.upper()
        if self.title:
            # Keep labels short for the CC menu
            short = self.title.strip()
            if len(short) > 28:
                short = short[:27] + "…"
            return short
        return "Embedded"


def list_embedded_subtitle_streams(video_path: Path) -> list[EmbeddedSubtitleStream]:
    probe = ffprobe_path()
    if probe is None or not video_path.is_file():
        return []

    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-select_streams",
                "s",
                "-show_entries",
                "stream=index,codec_name:stream_tags=language,title",
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
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    streams: list[EmbeddedSubtitleStream] = []
    for stream in payload.get("streams") or []:
        index = stream.get("index")
        if index is None:
            continue
        tags = stream.get("tags") or {}
        streams.append(
            EmbeddedSubtitleStream(
                stream_index=int(index),
                codec_name=stream.get("codec_name"),
                language=tags.get("language"),
                title=tags.get("title"),
            )
        )
    return streams


def extract_embedded_subtitle_vtt(
    video_path: Path,
    stream_index: int,
    output_path: Path,
) -> Path:
    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Extract the absolute stream index to WebVTT for the browser <track>.
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-map",
            f"0:{stream_index}",
            "-f",
            "webvtt",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 or not output_path.is_file():
        detail = (result.stderr or result.stdout or "unknown ffmpeg error").strip()
        raise RuntimeError(detail[-500:])
    return output_path
