import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { SubtitleTrack } from '../types'

type ActiveTrack =
  | { kind: 'off' }
  | { kind: 'external'; track: SubtitleTrack }
  | { kind: 'embedded'; key: string; label: string }

const SUBTITLE_SIZE_KEY = 'locflix.subtitleSizeBoost'
/** Extra pixels added on top of the base cue size (1.05rem + 2px). */
const SUBTITLE_SIZE_STEPS = [0, 2, 4, 6, 10, 14] as const
const SUBTITLE_SIZE_LABELS = ['Default', 'Large', 'Larger', 'XL', '2XL', '3XL'] as const

function externalLabel(track: SubtitleTrack): string {
  return `Locflix:${track.id}`
}

function isExternalTextTrack(track: TextTrack): boolean {
  return Boolean(track.label?.startsWith('Locflix:'))
}

function readStoredSizeIndex(): number {
  try {
    const raw = localStorage.getItem(SUBTITLE_SIZE_KEY)
    if (raw == null) return 0
    const idx = Number.parseInt(raw, 10)
    if (Number.isFinite(idx) && idx >= 0 && idx < SUBTITLE_SIZE_STEPS.length) return idx
  } catch {
    /* ignore */
  }
  return 0
}

export function PlayerPage() {
  const { id } = useParams()
  const videoRef = useRef<HTMLVideoElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState('Now playing')
  const [externalTracks, setExternalTracks] = useState<SubtitleTrack[]>([])
  const [embeddedTracks, setEmbeddedTracks] = useState<{ key: string; label: string }[]>([])
  const [active, setActive] = useState<ActiveTrack>({ kind: 'off' })
  const [ccOpen, setCcOpen] = useState(false)
  const [sizeIndex, setSizeIndex] = useState(readStoredSizeIndex)
  const lastSaved = useRef(0)
  const resumeReady = useRef(false)
  /** Anchor used to reject impossible currentTime jumps (e.g. 0 → 70s after 3s). */
  const progressAnchor = useRef({ media: 0, wall: Date.now() })
  const activeRef = useRef(active)
  const externalRef = useRef(externalTracks)
  const embeddedRef = useRef(embeddedTracks)

  activeRef.current = active
  externalRef.current = externalTracks
  embeddedRef.current = embeddedTracks

  const resetProgressAnchor = (mediaTime: number) => {
    progressAnchor.current = { media: mediaTime, wall: Date.now() }
  }

  const hasSubtitles = externalTracks.length > 0 || embeddedTracks.length > 0
  const sizeBoost = SUBTITLE_SIZE_STEPS[sizeIndex] ?? 0
  const sizeLabel = SUBTITLE_SIZE_LABELS[sizeIndex] ?? 'Default'
  const cueStyle = {
    '--cue-boost': `${sizeBoost}px`,
  } as CSSProperties

  const activeLabel = useMemo(() => {
    if (active.kind === 'off') return 'Off'
    if (active.kind === 'external') return active.track.label
    return active.label
  }, [active])

  function changeSubtitleSize(delta: -1 | 1) {
    setSizeIndex((prev) => {
      const next = Math.min(SUBTITLE_SIZE_STEPS.length - 1, Math.max(0, prev + delta))
      try {
        localStorage.setItem(SUBTITLE_SIZE_KEY, String(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const applyActiveTrack = useCallback((next: ActiveTrack) => {
    const video = videoRef.current
    if (!video) return
    for (let i = 0; i < video.textTracks.length; i += 1) {
      const track = video.textTracks[i]
      let show = false
      if (next.kind === 'external' && track.label === externalLabel(next.track)) {
        show = true
      } else if (next.kind === 'embedded' && !isExternalTextTrack(track)) {
        const key = `${track.kind}:${track.language}:${track.label}`
        show = key === next.key
      }
      track.mode = show ? 'showing' : 'disabled'
    }
  }, [])

  const setActiveTrack = useCallback(
    (next: ActiveTrack) => {
      setActive(next)
      applyActiveTrack(next)
    },
    [applyActiveTrack],
  )

  const cycleSubtitles = useCallback(() => {
    const options: ActiveTrack[] = [{ kind: 'off' }]
    for (const track of externalRef.current) {
      options.push({ kind: 'external', track })
    }
    for (const track of embeddedRef.current) {
      options.push({ kind: 'embedded', key: track.key, label: track.label })
    }
    if (options.length <= 1) return

    const current = activeRef.current
    const currentIndex = options.findIndex((opt) => {
      if (opt.kind !== current.kind) return false
      if (opt.kind === 'off') return true
      if (opt.kind === 'external' && current.kind === 'external') {
        return opt.track.id === current.track.id
      }
      if (opt.kind === 'embedded' && current.kind === 'embedded') {
        return opt.key === current.key
      }
      return false
    })
    setActiveTrack(options[(currentIndex + 1) % options.length])
  }, [setActiveTrack])

  useEffect(() => {
    if (!id) return
    resumeReady.current = false
    lastSaved.current = 0

    api
      .progress()
      .then((items) => {
        const match = items.find((p) => p.media_id === id)
        if (match?.title) setTitle(match.title)
      })
      .catch(() => undefined)

    const markResumeReady = (mediaTime = 0) => {
      resumeReady.current = true
      resetProgressAnchor(mediaTime)
    }

    api
      .getProgress(id)
      .then((p) => {
        const video = videoRef.current
        if (!video || p.position_seconds <= 5) {
          markResumeReady(video?.currentTime || 0)
          return
        }
        if (p.title) setTitle(p.title)

        const applyResume = () => {
          try {
            video.currentTime = p.position_seconds
          } finally {
            markResumeReady(p.position_seconds)
          }
        }

        // Metadata may already be available (event would never fire again).
        if (video.readyState >= 1) {
          applyResume()
        } else {
          video.addEventListener('loadedmetadata', applyResume, { once: true })
        }
      })
      .catch(() => {
        markResumeReady(videoRef.current?.currentTime || 0)
      })

    setActive({ kind: 'off' })
    setCcOpen(false)
    api
      .subtitles(id)
      .then((res) => {
        setExternalTracks(res.tracks)
        const preferred = (res.preferred_language || '').toLowerCase()
        if (!preferred) return
        const fileTracks = res.tracks.filter((track) => track.source === 'external')
        if (fileTracks.length === 0) return
        const match =
          fileTracks.find((track) => (track.language || '').toLowerCase() === preferred) ||
          fileTracks.find((track) => track.label.toLowerCase().includes(preferred)) ||
          fileTracks.find((track) => /^(eng|en|english)$/i.test(track.label)) ||
          fileTracks[0]
        // Defer until <track> elements mount.
        window.setTimeout(() => {
          setActiveTrack({ kind: 'external', track: match })
        }, 0)
      })
      .catch(() => setExternalTracks([]))
  }, [id, setActiveTrack])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const syncEmbedded = () => {
      const list: { key: string; label: string }[] = []
      for (let i = 0; i < video.textTracks.length; i += 1) {
        const track = video.textTracks[i]
        if (isExternalTextTrack(track)) continue
        if (track.kind !== 'subtitles' && track.kind !== 'captions') continue
        list.push({
          key: `${track.kind}:${track.language}:${track.label}`,
          label: track.label || track.language || `Track ${list.length + 1}`,
        })
      }
      setEmbeddedTracks(list)
      applyActiveTrack(activeRef.current)
    }

    syncEmbedded()
    video.textTracks.addEventListener('addtrack', syncEmbedded)
    video.textTracks.addEventListener('removetrack', syncEmbedded)
    video.addEventListener('loadedmetadata', syncEmbedded)

    return () => {
      video.textTracks.removeEventListener('addtrack', syncEmbedded)
      video.textTracks.removeEventListener('removetrack', syncEmbedded)
      video.removeEventListener('loadedmetadata', syncEmbedded)
    }
  }, [id, externalTracks, applyActiveTrack])

  useEffect(() => {
    const video = videoRef.current
    if (!video || !id) return

    const save = () => {
      // Wait until resume-seek finishes so we don't overwrite 24m progress with ~0s.
      if (!resumeReady.current) return
      if (!Number.isFinite(video.currentTime)) return
      // Mirror server rule: under 1 minute is not Continue Watching material.
      if (video.currentTime < 60) return

      // Reject impossible jumps (seen with some episode files reporting ~70s after a few seconds).
      const wallElapsed = (Date.now() - progressAnchor.current.wall) / 1000
      const maxBelievable = progressAnchor.current.media + wallElapsed + 20
      if (video.currentTime > maxBelievable) return

      const now = Date.now()
      if (now - lastSaved.current < 5000 && !video.paused) return
      lastSaved.current = now
      void api.putProgress(id, video.currentTime, video.duration || undefined).catch(() => undefined)
    }

    const onSeeked = () => {
      resetProgressAnchor(video.currentTime)
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return
      if (e.key === ' ' || e.key === 'k') {
        e.preventDefault()
        if (video.paused) void video.play()
        else video.pause()
      } else if (e.key === 'ArrowRight') {
        video.currentTime += 10
      } else if (e.key === 'ArrowLeft') {
        video.currentTime -= 10
      } else if (e.key === 'f') {
        if (document.fullscreenElement) void document.exitFullscreen()
        else void video.requestFullscreen()
      } else if (e.key.toLowerCase() === 'c') {
        if (externalRef.current.length > 0 || embeddedRef.current.length > 0) {
          cycleSubtitles()
        }
      }
    }

    video.addEventListener('pause', save)
    video.addEventListener('timeupdate', save)
    video.addEventListener('seeked', onSeeked)
    window.addEventListener('keydown', onKey)
    window.addEventListener('pagehide', save)

    return () => {
      save()
      video.removeEventListener('pause', save)
      video.removeEventListener('timeupdate', save)
      video.removeEventListener('seeked', onSeeked)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pagehide', save)
    }
  }, [id, cycleSubtitles])

  useEffect(() => {
    if (!ccOpen) return
    const onPointer = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) {
        setCcOpen(false)
      }
    }
    window.addEventListener('mousedown', onPointer)
    return () => window.removeEventListener('mousedown', onPointer)
  }, [ccOpen])

  if (!id) {
    return (
      <main className="page">
        <p className="error">Missing media id</p>
      </main>
    )
  }

  return (
    <main className="player-page">
      <div className="player-frame" style={cueStyle}>
        <video
          ref={videoRef}
          src={api.streamUrl(id)}
          controls
          autoPlay
          crossOrigin="anonymous"
          style={cueStyle}
          onError={() =>
            setError(
              'Playback failed. This file’s codec may not be supported in your browser (common with some .mkv files).',
            )
          }
        >
          {externalTracks.map((track) => (
            <track
              key={track.id}
              kind="subtitles"
              src={api.subtitleUrl(id, track.id)}
              srcLang={track.language ?? 'und'}
              label={externalLabel(track)}
            />
          ))}
        </video>

        {hasSubtitles && (
          <div className="cc-controls" ref={menuRef}>
            <button
              type="button"
              className={`cc-btn glass ${active.kind !== 'off' ? 'active' : ''}`}
              aria-label="Closed captions"
              aria-expanded={ccOpen}
              onClick={() => setCcOpen((v) => !v)}
            >
              CC
            </button>
            {ccOpen && (
              <div className="cc-menu glass" role="menu">
                <div className="cc-size-row">
                  <span className="cc-size-label">Text size</span>
                  <div className="cc-size-controls">
                    <button
                      type="button"
                      className="cc-size-btn"
                      aria-label="Decrease subtitle size"
                      disabled={sizeIndex <= 0}
                      onClick={() => changeSubtitleSize(-1)}
                    >
                      A−
                    </button>
                    <span className="cc-size-value">{sizeLabel}</span>
                    <button
                      type="button"
                      className="cc-size-btn"
                      aria-label="Increase subtitle size"
                      disabled={sizeIndex >= SUBTITLE_SIZE_STEPS.length - 1}
                      onClick={() => changeSubtitleSize(1)}
                    >
                      A+
                    </button>
                  </div>
                </div>
                <div className="cc-menu-divider" />
                <button
                  type="button"
                  className={active.kind === 'off' ? 'active' : ''}
                  onClick={() => {
                    setActiveTrack({ kind: 'off' })
                    setCcOpen(false)
                  }}
                >
                  Off
                </button>
                {externalTracks.map((track) => (
                  <button
                    key={track.id}
                    type="button"
                    className={
                      active.kind === 'external' && active.track.id === track.id ? 'active' : ''
                    }
                    onClick={() => {
                      setActiveTrack({ kind: 'external', track })
                      setCcOpen(false)
                    }}
                  >
                    {track.label}
                    <span className="muted">
                      {track.source === 'embedded' ? ' · in video' : ' · file'}
                    </span>
                  </button>
                ))}
                {embeddedTracks.map((track) => (
                  <button
                    key={track.key}
                    type="button"
                    className={active.kind === 'embedded' && active.key === track.key ? 'active' : ''}
                    onClick={() => {
                      setActiveTrack({
                        kind: 'embedded',
                        key: track.key,
                        label: track.label,
                      })
                      setCcOpen(false)
                    }}
                  >
                    {track.label}
                    <span className="muted"> · browser</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="player-meta glass">
        <h1 className="section-title" style={{ marginBottom: '0.35rem' }}>
          {title}
        </h1>
        <p className="muted" style={{ margin: '0 0 0.75rem' }}>
          Space play/pause · ←/→ seek · F fullscreen
          {hasSubtitles ? ` · C captions (${activeLabel})` : ''}
        </p>
        {error && <p className="error">{error}</p>}
        <Link className="btn" to="/">
          Back home
        </Link>
      </div>
    </main>
  )
}
