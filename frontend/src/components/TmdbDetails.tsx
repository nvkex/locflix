import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TmdbInfo } from '../types'

interface TmdbDetailsProps {
  kind: 'movie' | 'series'
  id: string | null | undefined
}

function formatRuntime(minutes: number | null | undefined): string | null {
  if (minutes == null || minutes <= 0) return null
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

export function TmdbDetails({ kind, id }: TmdbDetailsProps) {
  const [info, setInfo] = useState<TmdbInfo | null>(null)

  useEffect(() => {
    if (!id) {
      setInfo(null)
      return
    }
    let cancelled = false
    api
      .tmdbInfo(kind, id)
      .then((data) => {
        if (!cancelled) setInfo(data)
      })
      .catch(() => {
        if (!cancelled) setInfo(null)
      })
    return () => {
      cancelled = true
    }
  }, [kind, id])

  if (!info) return null

  const runtime = formatRuntime(info.runtime_minutes)
  const metaBits = [
    info.release_year != null ? String(info.release_year) : null,
    runtime,
    info.seasons != null ? `${info.seasons} season${info.seasons === 1 ? '' : 's'}` : null,
  ].filter(Boolean)

  return (
    <div className="tmdb-details">
      <div className="tmdb-details-top">
        {info.rating != null ? (
          <span className="tmdb-rating" title={info.vote_count ? `${info.vote_count} votes` : undefined}>
            ★ {info.rating.toFixed(1)}
          </span>
        ) : null}
        {metaBits.length > 0 ? <span className="tmdb-meta-bits">{metaBits.join(' · ')}</span> : null}
      </div>

      {info.genres.length > 0 ? (
        <div className="tmdb-genres">
          {info.genres.map((genre) => (
            <span key={genre} className="meta-badge">
              {genre}
            </span>
          ))}
        </div>
      ) : null}

      {info.tagline ? <p className="tmdb-tagline">{info.tagline}</p> : null}
      {info.overview ? <p className="tmdb-overview">{info.overview}</p> : null}

      {info.directors.length > 0 ? (
        <p className="tmdb-credit">
          <span className="muted">Director</span> {info.directors.join(', ')}
        </p>
      ) : null}
      {info.cast.length > 0 ? (
        <p className="tmdb-credit">
          <span className="muted">Cast</span> {info.cast.join(', ')}
        </p>
      ) : null}
    </div>
  )
}
