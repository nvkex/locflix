import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { MediaRow } from '../components/MediaRow'
import { PosterCard } from '../components/PosterCard'
import type { LibrarySummary, Movie, ProgressEntry, RecentItem, Show } from '../types'

function formatAdded(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'Recently added'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function itemLink(item: RecentItem): string {
  return item.kind === 'series' ? `/series/${item.id}` : `/movies/${item.id}`
}

export function HomePage() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [series, setSeries] = useState<Show[]>([])
  const [progress, setProgress] = useState<ProgressEntry[]>([])
  const [recent, setRecent] = useState<RecentItem[]>([])
  const [activeRecent, setActiveRecent] = useState(0)
  const [summary, setSummary] = useState<LibrarySummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [m, s, p, lib, r] = await Promise.all([
          api.movies(),
          api.series(),
          api.progress(),
          api.library(),
          api.recent(5),
        ])
        if (cancelled) return
        setMovies(m)
        setSeries(s)
        setProgress(p)
        setSummary(lib)
        setRecent(r)
        setActiveRecent(0)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load library')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (recent.length <= 1) return
    const timer = window.setInterval(() => {
      setActiveRecent((index) => (index + 1) % recent.length)
    }, 6500)
    return () => window.clearInterval(timer)
  }, [recent])

  const featured = recent[activeRecent] ?? null

  return (
    <main className="page">
      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-brand">Locflix</h1>
          {featured ? (
            <>
              <p className="hero-kicker">Recently added · {formatAdded(featured.added_at)}</p>
              <h2 className="hero-title">{featured.title}</h2>
              <p className="hero-meta">
                {featured.kind === 'series'
                  ? `TV Series${featured.episode_count != null ? ` · ${featured.episode_count} episodes` : ''}`
                  : 'Movie'}
                {summary
                  ? ` · ${summary.movies} movies · ${summary.series} series in your library`
                  : ''}
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary" to={itemLink(featured)}>
                  Open
                </Link>
                {featured.kind === 'movie' && featured.default_file_id && (
                  <Link className="btn" to={`/watch/${featured.default_file_id}`}>
                    Play
                  </Link>
                )}
              </div>
              {recent.length > 1 && (
                <div className="hero-dots" role="tablist" aria-label="Recently added titles">
                  {recent.map((item, index) => (
                    <button
                      key={`${item.kind}-${item.id}`}
                      type="button"
                      role="tab"
                      aria-selected={index === activeRecent}
                      className={index === activeRecent ? 'active' : ''}
                      aria-label={item.title}
                      onClick={() => setActiveRecent(index)}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <p>Your library. Your machine. Netflix energy.</p>
              <button
                className="btn"
                type="button"
                onClick={() => api.scan().then(() => location.reload())}
              >
                Scan library
              </button>
            </>
          )}
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      {progress.length > 0 && (
        <MediaRow title="Continue Watching">
          {progress.slice(0, 12).map((item) => {
            const total = Math.max(0, Math.floor(item.position_seconds))
            const mins = Math.floor(total / 60)
            const secs = total % 60
            const stamp = `${mins}:${secs.toString().padStart(2, '0')}`
            return (
              <PosterCard
                key={item.media_id}
                to={`/watch/${item.media_id}`}
                title={item.title ?? 'Resume'}
                subtitle={`${stamp} in`}
              />
            )
          })}
        </MediaRow>
      )}

      <MediaRow title="Movies">
        {movies.length === 0 ? (
          <p className="muted">No movies found. Add folders under your Movies directory and rescan.</p>
        ) : (
          movies.map((movie) => (
            <PosterCard
              key={movie.id}
              to={`/movies/${movie.id}`}
              title={movie.title}
              poster={movie.poster}
            />
          ))
        )}
      </MediaRow>

      <MediaRow title="Series">
        {series.length === 0 ? (
          <p className="muted">No series found. Use SXXEYY filenames inside each show folder.</p>
        ) : (
          series.map((show) => (
            <PosterCard
              key={show.id}
              to={`/series/${show.id}`}
              title={show.title}
              subtitle={`${show.episode_count} episodes`}
              poster={show.poster}
            />
          ))
        )}
      </MediaRow>
    </main>
  )
}
