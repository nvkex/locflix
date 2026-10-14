from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.catalog import catalog
from app.config import get_settings
from app.pathsafety import is_under_roots

router = APIRouter(tags=["stream"])


@router.get("/stream/{media_id}")
async def stream_media(media_id: str) -> FileResponse:
    path = catalog.get_file_path(media_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    settings = get_settings()
    if not is_under_roots(path, [settings.movies_dir, settings.series_dir]):
        raise HTTPException(status_code=403, detail="Path not allowed")

    # Starlette FileResponse supports HTTP Range for seekable playback.
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
        headers={"Accept-Ranges": "bytes"},
    )
