from pathlib import Path

from app.subtitles import find_external_subtitles, srt_to_vtt


def test_srt_to_vtt_basic():
    srt = """1
00:00:01,000 --> 00:00:03,500
Hello world

2
00:00:04,000 --> 00:00:05,000
Line two
"""
    vtt = srt_to_vtt(srt)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:03.500" in vtt
    assert "Hello world" in vtt
    assert "Line two" in vtt


def test_find_external_same_name_and_lang(tmp_path: Path):
    video = tmp_path / "Inception.mkv"
    video.write_bytes(b"x")
    (tmp_path / "Inception.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
    (tmp_path / "Inception.en.vtt").write_text("WEBVTT\n\n", encoding="utf-8")
    (tmp_path / "Other.srt").write_text("nope", encoding="utf-8")

    tracks = find_external_subtitles(video)
    assert len(tracks) == 2
    labels = {t.label for t in tracks}
    assert "Subtitles" in labels
    assert "EN" in labels


def test_find_external_subs_folder_and_episode_token(tmp_path: Path):
    video = tmp_path / "Show.S01E02.1080p.mkv"
    video.write_bytes(b"x")
    subs = tmp_path / "Subs"
    subs.mkdir()
    (subs / "English.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
    (tmp_path / "other.S01E02.en.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nEp\n", encoding="utf-8"
    )

    tracks = find_external_subtitles(video)
    assert len(tracks) == 2
    labels = {t.label for t in tracks}
    assert "English" in labels or "EN" in labels

