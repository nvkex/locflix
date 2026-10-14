from pathlib import Path

from app.scanner import parse_episode, scan_movies, scan_series


def test_parse_episode_variants():
    assert parse_episode("Breaking.Bad.S01E01.Pilot.mkv") == (1, 1)
    assert parse_episode("bb.s1e2.1080p.mkv") == (1, 2)
    assert parse_episode("anything_S02E05_extra.mp4") == (2, 5)
    assert parse_episode("movie.without.tags.mkv") is None


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
