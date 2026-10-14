from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.scanner import EPISODE_RE

SUBTITLE_EXTENSIONS = {".srt", ".vtt"}
SUB_DIR_NAMES = ("subs", "subtitles", "subtitle")


@dataclass(frozen=True)
class ExternalSubtitle:
    track_id: str
    path: Path
    label: str
    language: str | None
    format: str


def _language_from_name(video_stem: str, subtitle_stem: str) -> str | None:
    if subtitle_stem == video_stem:
        return None
    prefix = f"{video_stem}."
    if subtitle_stem.lower().startswith(prefix.lower()):
        lang = subtitle_stem[len(prefix) :]
        return lang or None
    return None


def _label_from_filename(path: Path) -> str:
    stem = path.stem
    # "English (CC).eng" → prefer trailing lang code if present
    if "." in stem:
        maybe_lang = stem.rsplit(".", 1)[-1]
        if 2 <= len(maybe_lang) <= 3 and maybe_lang.isalpha():
            return maybe_lang.upper()
    return stem


def _matches_video(video_path: Path, subtitle_path: Path) -> bool:
    video_stem = video_path.stem
    sub_stem = subtitle_path.stem

    if sub_stem == video_stem or sub_stem.lower().startswith(f"{video_stem.lower()}."):
        return True

    # Episode files often share only the SXXEYY token with sidecars.
    video_ep = EPISODE_RE.search(video_path.name)
    sub_ep = EPISODE_RE.search(subtitle_path.name)
    if video_ep and sub_ep:
        if int(video_ep.group("season")) == int(sub_ep.group("season")) and int(
            video_ep.group("episode")
        ) == int(sub_ep.group("episode")):
            return True

    return False


def _iter_subtitle_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files: list[Path] = []
    try:
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in SUBTITLE_EXTENSIONS:
                files.append(path)
    except OSError:
        return []
    return sorted(files, key=lambda p: p.name.lower())


def find_external_subtitles(video_path: Path) -> list[ExternalSubtitle]:
    """
    Find sidecar subtitles near a video.

    Matches:
    - same folder, same basename (Movie.mkv + Movie.srt / Movie.en.srt)
    - same folder, shared SxxEyy token (episode releases)
    - Subs/ or Subtitles/ folder next to the video (common YTS layout)
    """
    if not video_path.is_file():
        return []

    parent = video_path.parent
    candidates: list[Path] = []
    candidates.extend(_iter_subtitle_files(parent))

    try:
        for child in parent.iterdir():
            if child.is_dir() and child.name.lower() in SUB_DIR_NAMES:
                candidates.extend(_iter_subtitle_files(child))
    except OSError:
        pass

    # In a Subs/ folder for a single-title movie, include all language files
    # even when names don't match the video stem.
    videos_in_folder = [
        p
        for p in parent.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4v"}
    ] if parent.is_dir() else []
    single_title_folder = len(videos_in_folder) <= 1

    found: list[ExternalSubtitle] = []
    seen: set[Path] = set()

    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue

        in_subs_dir = path.parent.name.lower() in SUB_DIR_NAMES
        if not _matches_video(video_path, path):
            if not (in_subs_dir and single_title_folder):
                continue

        seen.add(resolved)
        if _matches_video(video_path, path) and path.parent == parent:
            language = _language_from_name(video_path.stem, path.stem)
            label = language.upper() if language else "Subtitles"
        else:
            language = None
            label = _label_from_filename(path)

        track_id = f"ext-{len(found)}"
        found.append(
            ExternalSubtitle(
                track_id=track_id,
                path=resolved,
                label=label,
                language=language,
                format=path.suffix.lower().lstrip("."),
            )
        )

    return found


_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2})[,.](\d{1,3})"
)


def _pad_ms(ms: str) -> str:
    return ms.ljust(3, "0")[:3]


def srt_to_vtt(content: str) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
    if not text:
        return "WEBVTT\n\n"

    blocks = re.split(r"\n\s*\n", text)
    out: list[str] = ["WEBVTT", ""]

    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue

        if re.fullmatch(r"\d+", lines[0].strip()):
            lines = lines[1:]
        if not lines:
            continue

        time_line = lines[0]
        match = _TIME_RE.search(time_line)
        if not match:
            continue

        start = f"{match.group(1)}.{_pad_ms(match.group(2))}"
        end = f"{match.group(3)}.{_pad_ms(match.group(4))}"
        payload = "\n".join(lines[1:]).strip()
        if not payload:
            continue

        out.append(f"{start} --> {end}")
        out.append(payload)
        out.append("")

    return "\n".join(out) + "\n"


def load_as_vtt(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".vtt":
        body = raw.lstrip("\ufeff")
        if not body.lstrip().upper().startswith("WEBVTT"):
            return "WEBVTT\n\n" + body
        return body
    if suffix == ".srt":
        return srt_to_vtt(raw)
    raise ValueError(f"Unsupported subtitle format: {suffix}")
