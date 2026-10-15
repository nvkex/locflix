from app.posters import pick_best_tmdb_result


def test_pick_best_tmdb_prefers_close_title_over_rank_order():
    results = [
        {
            "id": 52995,
            "title": "Red & White",
            "original_title": "Merah Putih",
            "release_date": "2009-08-13",
            "poster_path": "/merah.jpg",
        },
        {
            "id": 16869,
            "title": "Inglourious Basterds",
            "original_title": "Inglourious Basterds",
            "release_date": "2009-08-02",
            "poster_path": "/basterds.jpg",
        },
    ]
    best = pick_best_tmdb_result(results, "Inglourious Bastards", 2009, "movie")
    assert best is not None
    assert best["id"] == 16869


def test_pick_best_tmdb_rejects_weak_matches():
    results = [
        {
            "id": 1,
            "title": "Completely Different Film",
            "original_title": "Another Name",
            "release_date": "2009-01-01",
            "poster_path": "/x.jpg",
        }
    ]
    assert pick_best_tmdb_result(results, "Inglourious Bastards", 2009, "movie") is None
