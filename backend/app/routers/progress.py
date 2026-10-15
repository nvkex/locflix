from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response

from app import db
from app.catalog import catalog
from app.models import ProgressEntry, ProgressUpdate

router = APIRouter(tags=["progress"])

# Don't list (or keep) titles until at least 1 minute has been watched.
MIN_CONTINUE_WATCHING_SECONDS = 60.0


@router.get("/progress", response_model=list[ProgressEntry])
async def get_all_progress() -> list[ProgressEntry]:
    rows = await db.list_progress()
    entries: list[ProgressEntry] = []
    for row in rows:
        if row["position_seconds"] < MIN_CONTINUE_WATCHING_SECONDS:
            continue
        meta = catalog.get_title_meta(row["media_id"])
        if meta is None:
            # Skip progress for files no longer in the catalog
            continue
        kind, title = meta
        entries.append(
            ProgressEntry(
                media_id=row["media_id"],
                position_seconds=row["position_seconds"],
                duration_seconds=row["duration_seconds"],
                updated_at=row["updated_at"],
                title=title,
                kind=kind,
                poster=catalog.get_poster_for_file(row["media_id"]),
                has_subtitles=catalog.get_has_subtitles_for_file(row["media_id"]),
            )
        )
    return entries


@router.get("/progress/{media_id}", response_model=ProgressEntry)
async def get_one_progress(media_id: str) -> ProgressEntry:
    if catalog.get_file_path(media_id) is None:
        raise HTTPException(status_code=404, detail="Media not in catalog")
    row = await db.get_progress(media_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No progress saved")
    meta = catalog.get_title_meta(media_id)
    kind, title = meta if meta else (None, None)
    return ProgressEntry(
        media_id=row["media_id"],
        position_seconds=row["position_seconds"],
        duration_seconds=row["duration_seconds"],
        updated_at=row["updated_at"],
        title=title,
        kind=kind,
        poster=catalog.get_poster_for_file(media_id),
        has_subtitles=catalog.get_has_subtitles_for_file(media_id),
    )


@router.put("/progress/{media_id}", response_model=None)
async def put_progress(media_id: str, body: ProgressUpdate, response: Response):
    if catalog.get_file_path(media_id) is None:
        raise HTTPException(status_code=404, detail="Media not in catalog")

    # Under 1 minute: do not create/update Continue Watching.
    # Never delete existing progress here — the player often reports ~0s
    # briefly before resume-seek applies, which used to wipe real progress.
    if body.position_seconds < MIN_CONTINUE_WATCHING_SECONDS:
        response.status_code = 204
        return None

    updated_at = datetime.now(timezone.utc).isoformat()
    await db.upsert_progress(
        media_id=media_id,
        position_seconds=body.position_seconds,
        duration_seconds=body.duration_seconds,
        updated_at=updated_at,
    )
    meta = catalog.get_title_meta(media_id)
    kind, title = meta if meta else (None, None)
    return ProgressEntry(
        media_id=media_id,
        position_seconds=body.position_seconds,
        duration_seconds=body.duration_seconds,
        updated_at=updated_at,
        title=title,
        kind=kind,
        poster=catalog.get_poster_for_file(media_id),
        has_subtitles=catalog.get_has_subtitles_for_file(media_id),
    )
