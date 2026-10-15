from pathlib import Path

from app.scanner import (
    infer_episode_number,
    infer_season_from_path,
    parse_episode,
    resolve_episode,
    scan_movies,
    scan_series,
)


def test_parse_episode_variants():
    assert parse_episode("Breaking.Bad.S01E01.Pilot.mkv") == (1, 1)
    assert parse_episode("bb.s1e2.1080p.mkv") == (1, 2)
    assert parse_episode("anything_S02E05_extra.mp4") == (2, 5)
    assert parse_episode("movie.without.tags.mkv") is None


def test_infer_episode_number_from_dash_and_words():
    assert infer_episode_number("[Anime Time] Attack On Titan - 60.mkv") == 60
    assert infer_episode_number("[Anime Time] Attack On Titan - 88-91.mkv") == 88
    assert infer_episode_number("Show Episode 12.mp4") == 12
    assert infer_episode_number("Show E07.mkv") == 7
    assert infer_episode_number("random.trailer.mkv") is None


def test_infer_season_from_nested_folder(tmp_path: Path):
    show = tmp_path / "Attack On Titan"
    season = show / "[Anime Time] Attack On Titan (Season 4 Part 1)"
    season.mkdir(parents=True)
    video = season / "[Anime Time] Attack On Titan - 60.mkv"
    video.write_bytes(b"x")
    assert infer_season_from_path(video, show) == 4
    assert resolve_episode(video, show) == (4, 60)


def test_scan_movies_includes_all_videos(tmp_path: Path):
    movie_dir = tmp_path / "Inception (2010)"
    movie_dir.mkdir()
    (movie_dir / "release.name.1080p.mkv").write_bytes(b"a" * 100)
    (movie_dir / "bonus.mp4").write_bytes(b"b" * 50)
    (movie_dir / "notes.txt").write_text("ignore")
    (tmp_path / "The Matrix (1999).mp4").write_bytes(b"c" * 10)

    movies = scan_movies(tmp_path)
    assert len(movies) == 2
    by_title = {m.title: m for m in movies}
    assert "Inception (2010)" in by_title
    assert "The Matrix (1999)" in by_title
    assert len(by_title["Inception (2010)"].files) == 2
    assert len(by_title["The Matrix (1999)"].files) == 1
    largest = max(by_title["Inception (2010)"].files, key=lambda f: f.size)
    assert by_title["Inception (2010)"].default_file_id == largest.id
    assert by_title["Inception (2010)"].added_at is not None
    assert "T" in by_title["Inception (2010)"].added_at


def test_scan_series_regex_only(tmp_path: Path):
    show = tmp_path / "Breaking Bad"
    season = show / "Season 02"
    season.mkdir(parents=True)
    (show / "Breaking.Bad.S01E01.Pilot.mkv").write_bytes(b"x" * 10)
    (season / "bb.S02E05.mkv").write_bytes(b"y" * 10)
    (show / "trailer-no-tags.mp4").write_bytes(b"z" * 10)

    shows = scan_series(tmp_path)
    assert len(shows) == 1
    assert shows[0].title == "Breaking Bad"
    assert shows[0].episode_count == 2
    assert [s.number for s in shows[0].seasons] == [1, 2]
    assert shows[0].seasons[0].episodes[0].episode == 1
    assert shows[0].seasons[1].episodes[0].episode == 5


def test_scan_series_nested_season_folders_with_bare_episode_numbers(tmp_path: Path):
    show = tmp_path / "Attack On Titan"
    part1 = show / "[Anime Time] Attack On Titan (Season 4 Part 1)"
    part2 = show / "[Anime Time] Attack On Titan (Season 4 Part 2)"
    part1.mkdir(parents=True)
    part2.mkdir(parents=True)
    (part1 / "[Anime Time] Attack On Titan - 60.mkv").write_bytes(b"a" * 10)
    (part1 / "[Anime Time] Attack On Titan - 61.mkv").write_bytes(b"b" * 10)
    (part2 / "[Anime Time] Attack On Titan - 76.mkv").write_bytes(b"c" * 10)
    (part2 / "[Anime Time] Attack On Titan - 88-91.mkv").write_bytes(b"d" * 10)
    (show / "poster.jpg").write_bytes(b"img")

    shows = scan_series(tmp_path)
    assert len(shows) == 1
    assert shows[0].title == "Attack On Titan"
    assert shows[0].episode_count == 4
    assert [s.number for s in shows[0].seasons] == [4]
    episodes = [ep.episode for ep in shows[0].seasons[0].episodes]
    assert episodes == [60, 61, 76, 88]
