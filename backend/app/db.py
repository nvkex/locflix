from __future__ import annotations

import aiosqlite
from pathlib import Path

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
