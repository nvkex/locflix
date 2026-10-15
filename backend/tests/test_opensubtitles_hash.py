from pathlib import Path

from app.opensubtitles import movie_hash


def test_movie_hash_stable_for_temp_file(tmp_path: Path):
    path = tmp_path / "sample.bin"
    # Needs at least 128 KiB for the OpenSubtitles hash algorithm.
    path.write_bytes(b"\x01" * (65536 * 2 + 16))
    first = movie_hash(path)
    second = movie_hash(path)
    assert first is not None
    assert first == second
    assert len(first) == 16
