from __future__ import annotations

import re

_BRACKET_RE = re.compile(r"\[.*?\]")
_PAREN_RE = re.compile(r"\([^)]*\)")
_YEAR_PAREN_RE = re.compile(r"\((\d{4})\)")
_YEAR_TOKEN_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_SEASON_RANGE_RE = re.compile(r"S\d{1,2}\s*-\s*S\d{1,2}", re.IGNORECASE)
_EPISODE_RE = re.compile(r"S\d{1,2}E\d{1,2}", re.IGNORECASE)
_SEASON_RE = re.compile(r"\bS\d{1,2}\b", re.IGNORECASE)
# Folder names like "Legion Season 1" / "Show Series 02"
_SEASON_WORD_RE = re.compile(
    r"\b(?:season|series|seasons)\s*\d{1,2}\b",
    re.IGNORECASE,
)
_QUALITY_RE = re.compile(
    r"\b("
    r"1080p|720p|2160p|480p|4k|uhd|bluray|blu.?ray|bdrip|brrip|webrip|web.?dl|webdl|hdrip|"
    r"x264|x265|h264|h265|hevc|av1|hdr|dv|remux|yts|yify|extended|remastered|"
    r"repack|proper|limited|unrated|criterion|internal|"
    r"aac\d*|ac3|ddp?\d*|dts|opus|truehd|atmos|lpcm|"
    r"10bit|8bit|6ch|5\s*1|7\s*1|multi|dual|hindi|english|ita|eng|"
    r"heteam|crazy4tv|amzn|nf|dsnp|ma|web|bd|bone|fas|neonoir|supacvnt|v3sp4ev3r|prof|trix"
    r")\b",
    re.IGNORECASE,
)
_AUDIO_JUNK_RE = re.compile(
    r"\b(?:dd|ddp|aac|dts|ac3|lpcm)\s*\d*\b",
    re.IGNORECASE,
)


def parse_title_year(folder_name: str) -> tuple[str, int | None]:
    """
    Extract a clean TMDB search title and optional year from a release name.

    Scene-style loose files like ``Apex.2026.1080p.WEBRip...`` become
    title=``Apex``, year=``2026`` by taking the text before the year after
    normalizing ``.`` / ``_`` / ``-`` to spaces.
    """
    year: int | None = None

    paren_year = _YEAR_PAREN_RE.search(folder_name)
    if paren_year:
        year = int(paren_year.group(1))

    text = _BRACKET_RE.sub(" ", folder_name)
    text = _PAREN_RE.sub(" ", text)
    text = _SEASON_WORD_RE.sub(" ", text)
    text = _SEASON_RANGE_RE.sub(" ", text)
    text = _EPISODE_RE.sub(" ", text)
    text = _SEASON_RE.sub(" ", text)

    # Normalize separators first so quality tokens and years match as words.
    text = text.replace(".", " ").replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()

    if year is None:
        token = _YEAR_TOKEN_RE.search(text)
        if token:
            year = int(token.group(1))

    # For dotted releases, the real title is almost always everything before the year.
    if year is not None:
        before, sep, _after = text.partition(str(year))
        if sep and before.strip():
            text = before.strip()

    text = _QUALITY_RE.sub(" ", text)
    text = _AUDIO_JUNK_RE.sub(" ", text)
    # Lone digits left from things like "5 1" after separator normalization
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")

    return text or folder_name, year
