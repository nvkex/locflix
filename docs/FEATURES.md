# Locflix — Feature Notes

Brief how-it-works for the important behaviors. Companion to [DESIGN.md](DESIGN.md).

---

## Library scan

| Kind | Rule |
|------|------|
| **Movie (folder)** | Each subfolder of Movies = one title. All videos inside are included. |
| **Movie (loose)** | A video file directly in the Movies root = its own title. |
| **Series** | Each subfolder of Series = one show. Episodes via `SXXEYY`, or nested `Season N` folders + bare numbers (`Show - 60.mkv`). |

IDs are stable hashes of absolute paths. Default Play for a movie is the largest file.

---

## Title cleaning (TMDB / search prep)

`parse_title_year()` turns folder/file names into a clean query + optional year:

- Strip brackets, quality tags, `Season N`, episode tokens  
- Normalize `.` / `_` / `-` to spaces  
- Prefer text **before** the year (e.g. `Apex.2026.1080p…` → `Apex`, `2026`)  
- `Legion Season 1` → `Legion`

---

## Posters

Resolved in order (first hit wins):

1. **Cache** — `backend/data/posters/{id}.jpg`  
2. **Sidecar** — `poster.jpg` / `folder.jpg`, or `SameName.jpg` next to a loose file  
3. **Embedded** — attached cover art via ffmpeg  
4. **TMDB** — only if `LOCFLIX_TMDB_API_KEY` is set  

Startup scan attaches cached posters quickly; missing ones enrich in a **background** thread so the API stays responsive. Use **Fetch posters** (or `POST /api/posters/fetch?force=true`) to re-download.

### TMDB match picking

TMDB’s default rank order is not trusted. After search:

1. Score each result by **title similarity** (normalized string match against `title` / `original_title`)  
2. Boost if the release year matches; slight penalty if it’s far off  
3. Take the best score only if it’s above a minimum threshold (~0.55)  

Example: query `Inglourious Bastards` may rank *Merah Putih* first; Locflix still picks *Inglourious Basterds* because the title is much closer.

Continue Watching uses the **parent** movie/show poster (progress keys are file/episode ids).

---

## Recently added hero

`added_at` comes from filesystem birth/creation time (newest among title folder/file + its videos). Home rotates the latest titles from `GET /api/recent` with zoomed poster backdrops. Hero copy shows **title + year** (movies) or **title + season** (series).

---

## Streaming

`GET /api/stream/{id}` serves the file with HTTP **Range** (seekable `206`). Paths must resolve under the configured Movies/Series roots.

---

## Continue Watching

- Progress stored in SQLite, keyed by playable file/episode id  
- Listed only after **≥ 60 seconds** watched  
- Updates under 60s do **not** wipe existing progress (avoids resume race at ~0s)  
- Player saves on pause / interval / page hide  

---

## Subtitles

1. **External** — `.srt` / `.vtt` beside the video (same basename or language suffix; also `Subs/` folders)  
2. **Embedded** — listed with ffprobe, extracted to WebVTT with ffmpeg, cached under `data/subs/`  

Player exposes a **CC** menu and caption size (localStorage). Poster cards show a **CC** badge when a title has available subtitles.

When a title has **no** external or embedded subs, the detail page offers **Download English subtitles** (OpenSubtitles; requires `LOCFLIX_OPENSUBTITLES_API_KEY`). The `.en.srt` is saved next to the video and auto-selected on play.

---

## Detail metadata

Movie/series detail pages load `GET /api/media/{id}/metadata` (default/playable file) and show, under the poster (no section title):

File badges: quality (`1080p` / `720p`) and audio languages. A borderless table lists duration, size, container, video/audio codecs, frame rate, bitrate, and subtitles (via ffprobe).

---

## Config knobs

| Variable | Role |
|----------|------|
| `LOCFLIX_MOVIES_DIR` / `LOCFLIX_SERIES_DIR` | Library roots |
| `LOCFLIX_TMDB_API_KEY` | Optional poster enrichment |
| `LOCFLIX_OPENSUBTITLES_API_KEY` | Optional English subtitle downloads |
| `LOCFLIX_FETCH_POSTERS_ON_SCAN` | Background TMDB on scan/start |
| `LOCFLIX_SCAN_ON_START` | Auto-scan at boot |
| `LOCFLIX_DATA_DIR` | SQLite + poster/sub caches |

---

## What Locflix does *not* do

No transcoding for playback, no accounts/auth, no cloud library.
