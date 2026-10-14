from app.titleparse import parse_title_year


def test_parse_title_with_year_and_brackets():
    title, year = parse_title_year(
        "Coyote Vs. Acme (2026) [1080p] [WEBRip] [x265] [YTS.GG]"
    )
    assert year == 2026
    assert "Coyote" in title
    assert "Acme" in title
    assert "1080p" not in title


def test_parse_dotted_series_name():
    title, year = parse_title_year("Breaking.Bad.S01-S05.(2008).1080p.WEBRIP")
    assert year == 2008
    assert "Breaking" in title
    assert "Bad" in title


def test_parse_loose_dotted_movie_filenames():
    title, year = parse_title_year("Apex.2026.1080p.NF.WEBRip.DD5.1.x265.6CH-SupaCvnt")
    assert year == 2026
    assert title == "Apex"

    title, year = parse_title_year("Deep.Water.2026.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir")
    assert year == 2026
    assert title == "Deep Water"

    title, year = parse_title_year("Colony.2026.1080p.WEBRip.10bit.AAC2.0.x265-FaS")
    assert year == 2026
    assert title == "Colony"


def test_parse_removes_all_dots_before_search_shape():
    title, year = parse_title_year("Good.Fortune.2025.1080p.ITA-ENG.BluRay.x265.AAC-V3SP4EV3R")
    assert year == 2025
    assert "." not in title
    assert title == "Good Fortune"


def test_parse_strips_season_word_from_series_folders():
    title, year = parse_title_year("Legion Season 1")
    assert title == "Legion"
    assert year is None

    title, year = parse_title_year("Legion Season 1 S01 1080p 6CH BluRay x265-HETeam")
    assert title == "Legion"

