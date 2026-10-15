import asyncio

import aiosqlite

from app import db
from app.models import TmdbInfo


def test_upsert_and_get_tmdb_metadata(tmp_path):
    async def run() -> None:
        db_path = tmp_path / "test.db"
        await db.init_db(tmp_path, db_path)

        info = TmdbInfo(
            tmdb_id=8699,
            kind="movie",
            title="Anchorman: The Legend of Ron Burgundy",
            overview="Overview text",
            tagline="Tagline",
            rating=6.7,
            vote_count=100,
            genres=["Comedy", "Drama"],
            release_year=2004,
            release_date="2004-06-28",
            runtime_minutes=95,
            directors=["Adam McKay"],
            cast=["Will Ferrell", "Steve Carell"],
            seasons=None,
        )
        await db.upsert_tmdb_metadata("abc123", info)

        loaded = await db.get_tmdb_metadata("abc123")
        assert loaded is not None
        assert loaded.tmdb_id == 8699
        assert loaded.title.startswith("Anchorman")
        assert loaded.genres == ["Comedy", "Drama"]
        assert loaded.directors == ["Adam McKay"]
        assert loaded.cast == ["Will Ferrell", "Steve Carell"]

        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "SELECT media_id FROM tmdb_genres WHERE genre = ? COLLATE NOCASE",
                ("Comedy",),
            )
            rows = await cursor.fetchall()
            assert rows == [("abc123",)]

    asyncio.run(run())
