from contextlib import asynccontextmanager
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import catalog, rescan
from app.config import get_settings
from app.db import init_db
from app.lan.guard import LanAccessMiddleware
from app.lan.hub import lan_hub
from app.posters import enrich_all_posters
from app.routers import health, lan, library, metadata, posters, progress, stream, subtitles, tmdb

logger = logging.getLogger(__name__)


def _fetch_posters_background() -> None:
    try:
        settings = get_settings()
        enrich_all_posters(settings, catalog.movies, catalog.shows, force=False)
        catalog.rebuild_indexes()
        logger.info("Background poster enrichment finished")
    except Exception:
        logger.exception("Background poster enrichment failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    lan_hub.discovery_port = settings.lan_discovery_port
    await init_db(settings.data_dir, settings.db_path)
    if settings.scan_on_start:
        # Fast scan first so reload/startup isn't blocked by TMDB downloads.
        rescan(settings.movies_dir, settings.series_dir, fetch_posters=False)
        if settings.fetch_posters_on_scan:
            threading.Thread(target=_fetch_posters_background, daemon=True).start()
    try:
        yield
    finally:
        lan_hub.shutdown()


app = FastAPI(title="Locflix", version="0.1.0", lifespan=lifespan)

settings = get_settings()
cors_origins = settings.cors_origin_list
allow_all = cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LanAccessMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(subtitles.router, prefix="/api")
app.include_router(metadata.router, prefix="/api")
app.include_router(tmdb.router, prefix="/api")
app.include_router(posters.router, prefix="/api")
app.include_router(lan.router, prefix="/api")
