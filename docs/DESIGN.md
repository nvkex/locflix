# Locflix — Design Document

> A Netflix-like streaming UI for movies and TV shows stored on your local filesystem.

**Status:** Implemented MVP (docs aligned with code)  
**Version:** 0.1.0  
**Last updated:** 2026-10-14

---

## 1. Vision

Locflix is a self-hosted media browser and player. It looks and feels like Netflix, uses an iPhone-inspired glass (frosted / translucent) visual theme, and only catalogs content that already exists on disk. There is no cloud library, no DRM, and no remote content ingestion.

**Tagline:** *Your library. Your machine. Netflix energy.*

---

## 2. Goals & Non-Goals

### Goals

| Goal | Description |
|------|-------------|
| Local-only catalog | Movies from a configured Movies directory; series from a configured Series directory |
| Netflix-like UX | Home rows, recently-added hero, detail pages, seasons/episodes, fullscreen player |
| Glass UI | Frosted glass panels, soft blur, translucent chrome (iOS-inspired aesthetic) |
| Smooth playback | HTTP range streaming for seekable video playback in the browser |
| Posters | Sidecar / embedded / optional TMDB |
| Subtitles | Sidecar + embedded (ffmpeg extract) with CC UI |
| Optional Docker | First-class native install; Docker later |
| Open source | Clear docs, configurable paths, MIT license |

### Non-Goals (current)

- Transcoding / codec conversion pipelines for playback
- Multi-user accounts or authentication
- Subtitle *download* services (local/embedded only)
- Cloud sync or remote library hosting
- Mobile native apps (web responsive is enough)

---

## 3. Users & Use Cases

**Primary user:** Someone with a personal media folder structure who wants a polished browser UI instead of a file explorer.

**Core use cases**

1. Browse movies and series on a Netflix-style home page  
2. See recently added titles in the hero (filesystem created/birth time)  
3. Open a title detail view and play  
4. For series: pick season → episode  
5. Play with seek, captions, resume  
6. Search by movie/series title  

---

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React + TypeScript)                               │
│  Glass UI · Catalog · Detail · Player · CC                  │
└────────────────────────────┬────────────────────────────────┘
                             │ REST + video stream (HTTP Range)
┌────────────────────────────▼────────────────────────────────┐
│  Backend (Python / FastAPI)                                 │
│  Scan · Catalog · Stream · Progress · Posters · Subtitles   │
└────────────────────────────┬────────────────────────────────┘
                             │ read-only filesystem (+ optional TMDB HTTP)
┌────────────────────────────▼────────────────────────────────┐
│  Local media + cache                                        │
│  Movies / Series dirs · data/posters · data/subs · SQLite   │
└─────────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Choice |
|-------|--------|
| Frontend | React + TypeScript + Vite |
| Styling | Global CSS variables (glass tokens); fonts: Bricolage Grotesque + Outfit |
| Backend | FastAPI + uvicorn |
| Persistence | SQLite (watch progress) |
| Media tools | ffmpeg / ffprobe when available |

---

## 5. Media Library Model

### Default paths

| Library | Default path |
|---------|----------------|
| Movies | `D:\TV\Movies` |
| Series | `D:\TV\Series` |

```env
LOCFLIX_MOVIES_DIR=D:\TV\Movies
LOCFLIX_SERIES_DIR=D:\TV\Series
LOCFLIX_HOST=127.0.0.1
LOCFLIX_PORT=8787
LOCFLIX_TMDB_API_KEY=
LOCFLIX_FETCH_POSTERS_ON_SCAN=true
```

### Movies

Two shapes are supported:

1. **Folder title** — each immediate subdirectory is one movie; folder name = display title; all supported videos inside are included (filenames need not match).  
2. **Loose file** — a video file directly under the Movies root is one movie; filename stem = display title.

```
Movies/
  Inception (2010)/
    inception.2010.1080p.bluray.x264.mkv
    Inception-trailer.mp4
    poster.jpg
  The Matrix (1999)/
    MATRIX_1999_REMUX.mkv
  Apex.2026.1080p.WEBRip.x265.mkv          ✅ loose file title
```

| Rule | Behavior |
|------|----------|
| Folder title source | Folder name |
| Loose title source | Filename stem |
| Video inclusion (folder) | All supported extensions under that folder |
| Filename match | Not required |
| Default Play | Largest file by size |

### Series

Each immediate subdirectory of the Series root is one show (folder name = display title).

Episode resolution order:

1. `SXXEYY` in the filename (case-insensitive)  
2. Else season from a nested folder / show name (`Season 4`, `Season 4 Part 1`, `S04`) plus a bare episode number in the filename (`Show - 60.mkv`, `Episode 12`, `E07`; ranges like `88-91` use the first number)

Nested season folders are supported. Videos that match neither pattern are skipped.

### Supported video formats

`.mp4`, `.webm`, `.mkv`, `.avi`, `.mov`, `.m4v` (browser/codec dependent).

### Subtitles

- External: same basename `.srt` / `.vtt`, optional language suffix (`Movie.en.srt`), or files under `Subs/` / `Subtitles/` for single-title folders  
- Embedded: listed via ffprobe; extracted to WebVTT with ffmpeg and cached under `data/subs/`  
- Player exposes a **CC** control and caption text-size preference (localStorage)

### Posters

Resolution order per title:

1. Cache hit in `data/posters/{id}.jpg`  
2. Sidecar art (`poster.jpg` / `folder.jpg`, or `Stem.jpg` next to a loose video)  
3. Embedded attached cover (ffmpeg)  
4. TMDB search + download when `LOCFLIX_TMDB_API_KEY` is set  

**TMDB query cleaning:** normalize `.` / `_` / `-` to spaces; strip brackets/quality/season tokens; prefer text **before** the year for scene releases; strip `Season N` / `Series N` (e.g. `Legion Season 1` → `Legion`).  

- Folder movies: search uses **folder name**  
- Loose movies: search uses **filename stem**  
- Series: search uses **show folder name** (cleaned)

On startup, catalog scan is fast (cache attach only); missing TMDB posters enrich in a **background thread** when enabled.

### Recently added

`added_at` is derived from filesystem birth/creation time (`st_birthtime` when available, else `st_ctime` on Windows), taking the newest among the title folder/file and its videos. Home hero rotates the latest 5 via `GET /api/recent`.

---

## 6. Domain Model

```text
Library
  ├── Movie
  │     id, title, path, poster?, added_at?, default_file_id?
  │     └── VideoFile[]
  └── Show
        id, title, path, poster?, added_at?, episode_count
        └── Season → Episode[]   # from SXXEYY
```

IDs are stable SHA-256 prefixes of normalized absolute paths. Watch progress keys off concrete playable file ids (video/episode).

Continue Watching lists only entries with `position_seconds >= 60`. Short updates do not wipe existing progress.

---

## 7. API Surface

Base: `http://localhost:8787/api`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `GET` | `/library` | Summary counts + last scan |
| `GET` | `/movies` | List movies |
| `GET` | `/movies/{id}` | Movie detail |
| `GET` | `/series` | List shows |
| `GET` | `/series/{id}` | Show + seasons/episodes |
| `GET` | `/recent?limit=` | Latest titles by `added_at` |
| `GET` | `/search?q=` | Title search |
| `POST` | `/scan` | Rescan (+ poster enrich if configured) |
| `GET` | `/stream/{id}` | Video stream (Range / 206) |
| `GET` | `/progress` | Continue-watching list |
| `GET` | `/progress/{id}` | One progress row |
| `PUT` | `/progress/{id}` | Upsert (204 if &lt; 60s) |
| `GET` | `/media/{id}/subtitles` | List subtitle tracks |
| `GET` | `/media/{id}/subtitles/{track}` | WebVTT body |
| `GET` | `/posters/{id}` | Cached JPEG |
| `POST` | `/posters/fetch` | Enrich missing posters |

---

## 8. Frontend UX

1. **Home** — Locflix brand + rotating recently-added hero; Continue Watching; Movies; Series  
2. **Movies / Series** — responsive grids  
3. **Detail** — poster + play / file or episode lists  
4. **Player** — native `<video>`, CC menu, caption size, keyboard shortcuts  

Cards: show poster image alone when available; fallback title overlay when not. Caption under card shows title (+ episode count for series).

Nav: full-width glass header (no pill radius). Carousel rows: eased arrow scroll + themed scrollbars.

---

## 9. Security & Safety

1. Path allowlist — only under configured Movies/Series roots  
2. Resolve streams/subs/posters by media id only  
3. Default bind `127.0.0.1`  
4. No auth — LAN exposure shares the library  

---

## 10. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCFLIX_MOVIES_DIR` | `D:\TV\Movies` | Movies root |
| `LOCFLIX_SERIES_DIR` | `D:\TV\Series` | Series root |
| `LOCFLIX_HOST` | `127.0.0.1` | Bind address |
| `LOCFLIX_PORT` | `8787` | API port |
| `LOCFLIX_DATA_DIR` | `./data` | SQLite + posters + subs cache |
| `LOCFLIX_SCAN_ON_START` | `true` | Auto-scan at boot |
| `LOCFLIX_CORS_ORIGINS` | Vite dev origins | Comma-separated |
| `LOCFLIX_TMDB_API_KEY` | _(empty)_ | Optional TMDB v3 key |
| `LOCFLIX_FETCH_POSTERS_ON_SCAN` | `true` | Background/on-scan poster enrich |

Frontend Vite proxy: `/api` → `http://127.0.0.1:8787`.

---

## 11. Repository Layout

```
locflix/
  README.md
  LICENSE
  .env.example
  docs/
    DESIGN.md
    DEVELOPMENT_PLAN.md
  frontend/                 # React + TS (Vite)
  backend/
    app/                    # FastAPI package
    tests/
    requirements.txt
  scripts/dev.ps1
```

Docker packaging is planned, not required.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Browser can’t play some `.mkv` codecs | Clear player error state |
| TMDB miss on release names | Aggressive title cleaning; year-before-cut; Season N strip |
| Slow poster downloads | Cache on disk; background enrich on startup |
| Resume wipe from 0s saves | Ignore &lt; 60s updates; don’t delete existing progress |
| Reload blocked by poster fetch | Startup scan without blocking TMDB |

---

## 13. Future Ideas

- Full NFO / Kodi metadata import  
- Optional TMDB overview/backdrop on detail pages  
- Favorites / watchlist  
- ffmpeg remux/transcode for incompatible files  
- LAN auth toggle  
- Watch-folder auto-rescan  
- Docker Compose packaging  

---

## 14. Decision Log

| Decision | Choice | Why |
|----------|--------|-----|
| Backend | Python / FastAPI | File IO + streaming APIs |
| Frontend | React + TypeScript | Component ecosystem for media UI |
| DB | SQLite | Zero infra |
| Posters | Sidecar → embedded → TMDB | Works offline first; enrichment optional |
| Docker | Optional / later | Keep native Windows paths frictionless |
| Auth | None for now | Personal single-user tool |
