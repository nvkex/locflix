import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { MediaMetadata } from '../components/MediaMetadata'
import { TmdbDetails } from '../components/TmdbDetails'
import type { Show } from '../types'

export function ShowDetailPage() {
  const { id } = useParams()
  const [show, setShow] = useState<Show | null>(null)
  const [seasonNum, setSeasonNum] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .show(id)
      .then((data) => {
        setShow(data)
        setSeasonNum(data.seasons[0]?.number ?? null)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load series'))
  }, [id])

  const season = useMemo(
    () => show?.seasons.find((s) => s.number === seasonNum) ?? null,
    [show, seasonNum],
  )

  if (error) {
    return (
      <main className="page">
        <p className="error">{error}</p>
      </main>
    )
  }

  if (!show) {
    return (
      <main className="page">
        <p className="muted">Loading…</p>
      </main>
    )
  }

  const firstEpisode = show.seasons[0]?.episodes[0]
  const metaEpisode = season?.episodes[0] ?? firstEpisode

  return (
    <main className="page">
      <div className="detail-layout">
        <aside className="detail-aside">
          <div className={`poster${show.poster ? ' has-image' : ''}`} style={{ minHeight: 360 }}>
            {show.poster ? <img src={show.poster} alt={show.title} /> : <span>{show.title}</span>}
          </div>
          <TmdbDetails kind="series" id={show.id} />
          <MediaMetadata
            mediaId={metaEpisode?.id ?? show.id}
            onSubtitlesChanged={(has) =>
              setShow((prev) => (prev ? { ...prev, has_subtitles: has } : prev))
            }
          />
        </aside>
        <section className="detail-panel glass">
          <h1>{show.title}</h1>
          <p className="muted">
            {show.seasons.length} season{show.seasons.length === 1 ? '' : 's'} · {show.episode_count}{' '}
            episodes
          </p>
          {firstEpisode && (
            <p style={{ marginTop: '1.25rem' }}>
              <Link className="btn btn-primary" to={`/watch/${firstEpisode.id}`}>
                Play S{firstEpisode.season.toString().padStart(2, '0')}E
                {firstEpisode.episode.toString().padStart(2, '0')}
              </Link>
            </p>
          )}

          <div className="season-tabs">
            {show.seasons.map((s) => (
              <button
                key={s.number}
                type="button"
                className={s.number === seasonNum ? 'active' : ''}
                onClick={() => setSeasonNum(s.number)}
              >
                Season {s.number}
              </button>
            ))}
          </div>

          <ul className="episode-list">
            {season?.episodes.map((ep) => (
              <li key={ep.id}>
                <div>
                  <div>
                    S{ep.season.toString().padStart(2, '0')}E{ep.episode.toString().padStart(2, '0')}
                  </div>
                  <div className="muted" style={{ fontSize: '0.85rem' }}>
                    {ep.filename}
                  </div>
                </div>
                <Link className="btn" to={`/watch/${ep.id}`}>
                  Play
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}