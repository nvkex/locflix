# Locflix — Development Plan

> Phased roadmap from empty repo → usable MVP → open-source-ready release.

**Companion docs:** [DESIGN.md](DESIGN.md) · [README.md](../README.md)  
**Default libraries:** `D:\TV\Movies`, `D:\TV\Series` (configurable)  
**Last updated:** 2026-10-14

---

## Guiding principles

1. **Docs → scaffold → vertical slice → polish** — ship a playable path early  
2. **Native first, Docker optional** — Windows paths should work without containers  
3. **Small PRs / clear milestones** — each phase leaves the app runnable  
4. **Config over hardcoding** — never assume `D:\` for other contributors  
5. **Glass Netflix UX** — visual quality is a feature, not a late coat of paint  

---

## Phase 0 — Documentation & project framing ✅

**Goal:** Align on product, architecture, and open-source posture before code.

| Deliverable | Status |
|-------------|--------|
| Design document (`docs/DESIGN.md`) | Done |
| README (`README.md`) | Done |
| Development plan (this file) | Done |

**Exit criteria:** Stakeholders agree on stack (React/TS + FastAPI), paths, and MVP scope.

---

## Phase 1 — Foundation & scaffold ✅

**Goal:** Empty app that boots frontend + backend with shared config.

### Backend

- [x] FastAPI project under `backend/`
- [x] Settings via env (`LOCFLIX_*`) with defaults for Movies/Series dirs
- [x] `GET /api/health`
- [x] SQLite data directory bootstrap
- [x] `.env.example`, `requirements.txt`

### Frontend

- [x] Vite + React + TypeScript under `frontend/`
- [x] App shell: nav, routes (Home / Movies / Series)
- [x] Design tokens for glass theme (CSS variables)
- [x] Dev proxy `/api` → backend

### Repo hygiene

- [x] `.gitignore` (node, venv, `.env`, `data/`)
- [x] MIT `LICENSE`
- [x] `scripts/dev.ps1` for local run

**Exit criteria:** Met — uvicorn + Vite run; health check works; glass shell renders.

---

## Phase 2 — Library scanning & catalog API ✅

**Goal:** Turn folders into a queryable catalog.

- [x] Movies scanner: folder titles + **loose** videos in Movies root
- [x] Folder movies include **all** supported videos (filenames need not match)
- [x] Series scanner: show folders; videos under show tree
- [x] Episode parse via `S(?P<season>\d{1,2})E(?P<episode>\d{1,2})`; skip non-matches
- [x] In-memory catalog + SQLite for progress
- [x] APIs: movies, series, search, recent, scan
- [x] `POST /scan` + scan-on-start
- [x] Path allowlist helpers
- [x] Unit tests for `SXXEYY` / title parse helpers

**Exit criteria:** Met — API returns real titles; movie detail lists videos; episodes require `SXXEYY`.

---

## Phase 3 — Browse UI (Netflix + glass) ✅

**Goal:** Catalog feels like a streaming home screen.

- [x] Home page with horizontal rows (Continue Watching, Movies, Series)
- [x] Recently-added hero (`GET /api/recent`)
- [x] Poster cards (image or title fallback)
- [x] Title detail pages + Play CTA
- [x] Series detail: seasons + episodes
- [x] Loading / empty / error states
- [x] Responsive layout
- [x] Motion: hover scale, carousel easing, themed scrollbars

**Exit criteria:** Met — full local library browseable in the UI.

---

## Phase 4 — Playback ✅

**Goal:** Watch something end-to-end in the browser.

- [x] `GET /api/stream/{id}` with HTTP Range (`206`)
- [x] Secure resolve: media id → path under allowlisted roots only
- [x] React player page (native `<video>`)
- [x] Controls: play/pause, seek, volume, fullscreen
- [x] Keyboard shortcuts
- [x] Unsupported-codec / load-error UI
- [x] Play wired from movie + episode detail
- [x] Subtitles: sidecar + embedded extract; CC menu + caption size

**Exit criteria:** Met — browser-supported files play with seek and captions.

---

## Phase 5 — Continue watching, search & posters ✅

**Goal:** Habit loops, findability, and art.

- [x] `PUT/GET /api/progress` + Continue Watching row
- [x] Persist on pause / interval / page hide
- [x] Resume from saved position
- [x] Only persist / show progress after ≥ 60 seconds watched
- [x] `GET /api/search?q=` + frontend search
- [x] Posters: sidecar → embedded → TMDB (`LOCFLIX_TMDB_API_KEY`)
- [x] Title cleaning for TMDB (dots, year cut, Season N, quality tags)
- [x] `GET /api/posters/{id}`, `POST /api/posters/fetch`
- [x] Background poster enrich on startup (non-blocking)

**Exit criteria:** Met — progress survives refresh; search works; posters enrich when key is set.

---

## Phase 6 — Packaging & open-source readiness ○

**Goal:** Others can run Locflix without tribal knowledge.

- [ ] Optional `docker/Dockerfile` + `docker-compose.yml` with volume examples
- [ ] Document native Windows vs Docker path mapping
- [ ] `CONTRIBUTING.md` (setup, code style, PR checklist)
- [ ] Issue / PR templates (optional)
- [ ] Smoke-test checklist in docs
- [ ] First tagged release (`v0.1.0`) when MVP is stable
- [x] README + design + plan kept accurate with implemented features

**Exit criteria:** Fresh clone → configure paths → run in &lt; 15 minutes (native or Docker).

**Estimate:** 1–2 days

---

## Phase 7 — Post-MVP (backlog)

| Idea | Value | Notes |
|------|-------|-------|
| NFO / Kodi metadata import | Richer local metadata | Sidecar posters already work |
| TMDB overview / backdrop on detail | Richer detail pages | Poster fetch already shipped |
| Favorites / watchlist | Personalization | |
| ffmpeg remux/transcode | Broader `.mkv` support | |
| LAN auth toggle | Safer home-network sharing | |
| Watch folder / auto-rescan | Less manual scan | |
| Mark finished / clear progress | Progress UX polish | |
| Serve built frontend from FastAPI | Single-process deploy | |
| Docker Compose packaging | Easy install path | Phase 6 |

---

## Milestone map

```text
M0  Docs                          ✅
M1  Scaffold + glass shell        ✅
M2  Scan + catalog API            ✅
M3  Browse UI                     ✅
M4  Stream + player + subs        ✅
M5  Progress + search + posters   ✅
M6  Docker optional + OSS polish  ○  ← next
```

---

## Testing strategy

| Layer | Approach |
|-------|----------|
| Parser / path safety | Backend unit tests with fixture trees |
| API | FastAPI `TestClient` against temp media dirs |
| UI | Manual checklist first; Playwright smoke later |
| Streaming | Manual seek tests; verify `206` responses |

---

## Definition of Done — MVP (v0.1.0)

- [x] Movies from configured Movies dir appear in UI (folders + loose files)
- [x] Series from configured Series dir appear with seasons/episodes
- [x] Playback works for browser-supported files with seek
- [x] Continue Watching persists (≥ 60s rule)
- [x] Subtitles (sidecar + embedded) + CC UI
- [x] Auto posters (sidecar / embedded / TMDB)
- [x] Glass Netflix-like UX on Home + Detail + Player
- [x] README + design + plan accurate
- [ ] Docker optional and documented
- [ ] CONTRIBUTING basics + tagged `v0.1.0`

---

## Roles / ownership (solo-friendly)

| Track | Focus |
|-------|--------|
| A — Backend | Scan, stream, progress, posters, subs, tests |
| B — Frontend | Glass UI, browse, player, CC |
| C — Packaging | Docker, docs, release |

---

## Resolved decisions

1. **Frontend serving:** Vite in dev; FastAPI static mount still optional for production.  
2. **Posters:** Sidecar → embedded → TMDB (not placeholders-only).  
3. **Bind default:** `127.0.0.1`; document LAN if changing to `0.0.0.0`.  

---

## Next action

**Phase 6** — Docker packaging, CONTRIBUTING, smoke checklist, tag `v0.1.0`.
