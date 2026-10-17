# Locflix

**Your library. Your machine. Netflix energy.**

Locflix is an open-source, Netflix-style web app for browsing and playing **movies and TV shows stored on your local filesystem**. No cloud library. No subscriptions. Just a polished UI over the files you already have.

Default libraries (configurable):

| Library | Default path |
|---------|----------------|
| Movies | `D:\TV\Movies` |
| Series | `D:\TV\Series` |

> **Status:** Usable MVP - catalog, multi-theme UI, streaming player, continue watching, subtitles, and TMDB posters are implemented. Docker packaging is still optional/future.  
> See [docs/DESIGN.md](docs/DESIGN.md) and [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

---

## Features

- Netflix-like home (recently added hero), rows, title detail, and fullscreen player
- Multi-theme UI: **Glass** (default) and **GenUI** (Veriguard-style cyber-security)
- **LAN streaming** - share this library to other devices on the same Wi‑Fi (seeder/leecher)
- Catalog from local **Movies** and **Series** directories
- Movies as **folders** or **loose** `.mp4` / `.mkv` / etc. in the Movies root
- Season / episode navigation (`SXXEYY` filenames)
- HTTP range streaming with seek
- Continue Watching (SQLite; only after ≥ 1 minute watched)
- External + embedded subtitles (CC button; ffmpeg extracts in-video softsubs)
- Auto posters: local sidecar → embedded cover → **TMDB** (optional API key)
- Search, rescan, fetch posters
- Configurable paths for any OS
- **Optional** Docker later - native install is first-class today

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript (Vite) |
| Backend | Python (FastAPI) |
| Data | SQLite + on-disk poster/subtitle cache |
| Optional tools | ffmpeg / ffprobe (embedded posters & subtitles) |

---

## Quick start

### Prerequisites

- Node.js 20+
- Python 3.11+
- A Movies folder and/or Series folder with video files
- Optional but recommended: [ffmpeg](https://ffmpeg.org/) on `PATH` (embedded art/subs)
- Optional: free [TMDB API key](https://www.themoviedb.org/settings/api) for posters

### Configuration

```bash
cp .env.example .env
```

Edit `.env` as needed:

```env
LOCFLIX_MOVIES_DIR=D:\TV\Movies
LOCFLIX_SERIES_DIR=D:\TV\Series
LOCFLIX_HOST=127.0.0.1
LOCFLIX_PORT=8787
LOCFLIX_TMDB_API_KEY=your_tmdb_v3_key
LOCFLIX_FETCH_POSTERS_ON_SCAN=true
```

### Run locally

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8787

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open the Vite URL (typically `http://localhost:5173`).

On Windows you can also run `powershell -File scripts/dev.ps1`.

After setting a TMDB key, use **Fetch posters** in the header (or restart - posters also enrich in the background on startup).

### Docker (optional)

Not packaged yet. Native install is the supported path today.

---

## Library layout

**Movies** - folder per title **or** a loose video file in the Movies root.

```text
Movies/
  Inception (2010)/                 ← folder title
    inception.2010.1080p.mkv
    bonus-feature.mp4
  The Matrix (1999)/
    MATRIX_1999_REMUX.mkv
  Apex.2026.1080p.WEBRip.x265.mkv   ← loose file = its own title
```

**Series** - one folder per show. Episode files must contain `SXXEYY` (case-insensitive). Nested season folders are optional.

```text
Series/
  Breaking Bad/
    Breaking.Bad.S01E01.Pilot.mkv
    Season 02/
      bb.S02E05.1080p.mkv
  Legion Season 1/                  ← display name can include "Season 1"
    Crazy4TV.com - Legion.S01E01....mkv
```

---

## Posters

Resolved in order:

1. Local `poster.jpg` / `folder.jpg` (or `MovieName.jpg` next to a loose file)
2. Cover art embedded in the video (ffmpeg)
3. TMDB search using a cleaned title (dots → spaces, text before year, strip `Season N`, quality tags, etc.)

Cached under `backend/data/posters/`.

---

## Subtitles

- Sidecar `.srt` / `.vtt` with the same basename (or language suffix) as the video
- Softsubs inside the container extracted via ffmpeg when present
- Player **CC** menu + text size controls

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [Design document](docs/DESIGN.md) | Architecture, UX, API, security, config |
| [Feature notes](docs/FEATURES.md) | Brief how-it-works (posters, TMDB, progress, etc.) |
| [Development plan](docs/DEVELOPMENT_PLAN.md) | Phased roadmap and milestones |

---

## Contributing

1. Read the [design doc](docs/DESIGN.md)  
2. Check the [development plan](docs/DEVELOPMENT_PLAN.md)  
3. Open an issue for larger ideas before coding  

---

## License

[MIT](LICENSE)

---

## Disclaimer

Locflix only plays files already present on your machine. You are responsible for ensuring you have the right to store and play your media. This project does not provide copyrighted content.
