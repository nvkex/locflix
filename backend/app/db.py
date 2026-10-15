from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite
from pathlib import Path

from app.models import TmdbInfo

_DB_PATH: Path | None = None


async def init_db(data_dir: Path, db_path: Path) -> None:
    global _DB_PATH
    data_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = db_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_progress (
                media_id TEXT PRIMARY KEY,
                position_seconds REAL NOT NULL,
                duration_seconds REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS subtitle_prefs (
                media_id TEXT PRIMARY KEY,
                preferred_language TEXT NOT NULL DEFAULT 'en',
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tmdb_metadata (
                media_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                tmdb_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                overview TEXT,
                tagline TEXT,
                rating REAL,
                vote_count INTEGER,
                release_year INTEGER,
                release_date TEXT,
                runtime_minutes INTEGER,
                directors_json TEXT NOT NULL DEFAULT '[]',
                cast_json TEXT NOT NULL DEFAULT '[]',
                seasons INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tmdb_genres (
                media_id TEXT NOT NULL,
                genre TEXT NOT NULL,
                PRIMARY KEY (media_id, genre),
                FOREIGN KEY (media_id) REFERENCES tmdb_metadata(media_id) ON DELETE CASCADE
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tmdb_genres_genre ON tmdb_genres(genre)"
        )
        await db.commit()


def _require_db() -> Path:
    if _DB_PATH is None:
        raise RuntimeError("Database not initialized")
    return _DB_PATH


async def upsert_progress(
    media_id: str,
    position_seconds: float,
    duration_seconds: float | None,
    updated_at: str,
) -> None:
    async with aiosqlite.connect(_require_db()) as db:
        await db.execute(
            """
            INSERT INTO watch_progress (media_id, position_seconds, duration_seconds, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                position_seconds = excluded.position_seconds,
                duration_seconds = excluded.duration_seconds,
                updated_at = excluded.updated_at
            """,
            (media_id, position_seconds, duration_seconds, updated_at),
        )
        await db.commit()


async def list_progress() -> list[dict]:
    async with aiosqlite.connect(_require_db()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT media_id, position_seconds, duration_seconds, updated_at
            FROM watch_progress
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_progress(media_id: str) -> dict | None:
    async with aiosqlite.connect(_require_db()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT media_id, position_seconds, duration_seconds, updated_at
            FROM watch_progress
            WHERE media_id = ?
            """,
            (media_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_progress(media_id: str) -> None:
    async with aiosqlite.connect(_require_db()) as db:
        await db.execute("DELETE FROM watch_progress WHERE media_id = ?", (media_id,))
        await db.commit()


async def upsert_subtitle_pref(media_id: str, preferred_language: str, updated_at: str) -> None:
    async with aiosqlite.connect(_require_db()) as db:
        await db.execute(
            """
            INSERT INTO subtitle_prefs (media_id, preferred_language, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                preferred_language = excluded.preferred_language,
                updated_at = excluded.updated_at
            """,
            (media_id, preferred_language, updated_at),
        )
        await db.commit()


async def get_subtitle_pref(media_id: str) -> dict | None:
    async with aiosqlite.connect(_require_db()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT media_id, preferred_language, updated_at
            FROM subtitle_prefs
            WHERE media_id = ?
            """,
            (media_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


async def get_tmdb_metadata(media_id: str) -> TmdbInfo | None:
    async with aiosqlite.connect(_require_db()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT media_id, kind, tmdb_id, title, overview, tagline, rating, vote_count,
                   release_year, release_date, runtime_minutes, directors_json, cast_json, seasons
            FROM tmdb_metadata
            WHERE media_id = ?
            """,
            (media_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        genres_cursor = await db.execute(
            """
            SELECT genre FROM tmdb_genres
            WHERE media_id = ?
            ORDER BY genre COLLATE NOCASE
            """,
            (media_id,),
        )
        genre_rows = await genres_cursor.fetchall()
        genres = [str(g["genre"]) for g in genre_rows]

        return TmdbInfo(
            tmdb_id=int(row["tmdb_id"]),
            kind=str(row["kind"]),
            title=str(row["title"]),
            overview=row["overview"],
            tagline=row["tagline"],
            rating=row["rating"],
            vote_count=row["vote_count"],
            genres=genres,
            release_year=row["release_year"],
            release_date=row["release_date"],
            runtime_minutes=row["runtime_minutes"],
            directors=_parse_json_list(row["directors_json"]),
            cast=_parse_json_list(row["cast_json"]),
            seasons=row["seasons"],
        )


async def upsert_tmdb_metadata(media_id: str, info: TmdbInfo) -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_require_db()) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """
            INSERT INTO tmdb_metadata (
                media_id, kind, tmdb_id, title, overview, tagline, rating, vote_count,
                release_year, release_date, runtime_minutes, directors_json, cast_json,
                seasons, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                kind = excluded.kind,
                tmdb_id = excluded.tmdb_id,
                title = excluded.title,
                overview = excluded.overview,
                tagline = excluded.tagline,
                rating = excluded.rating,
                vote_count = excluded.vote_count,
                release_year = excluded.release_year,
                release_date = excluded.release_date,
                runtime_minutes = excluded.runtime_minutes,
                directors_json = excluded.directors_json,
                cast_json = excluded.cast_json,
                seasons = excluded.seasons,
                updated_at = excluded.updated_at
            """,
            (
                media_id,
                info.kind,
                info.tmdb_id,
                info.title,
                info.overview,
                info.tagline,
                info.rating,
                info.vote_count,
                info.release_year,
                info.release_date,
                info.runtime_minutes,
                json.dumps(info.directors),
                json.dumps(info.cast),
                info.seasons,
                updated_at,
            ),
        )
        await db.execute("DELETE FROM tmdb_genres WHERE media_id = ?", (media_id,))
        for genre in info.genres:
            cleaned = genre.strip()
            if not cleaned:
                continue
            await db.execute(
                """
                INSERT OR IGNORE INTO tmdb_genres (media_id, genre)
                VALUES (?, ?)
                """,
                (media_id, cleaned),
            )
        await db.commit()
