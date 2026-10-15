import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { MediaRow } from '../components/MediaRow'
import { PosterCard } from '../components/PosterCard'
import type { Movie, ProgressEntry, RecentItem, Show } from '../types'

function itemLink(item: RecentItem): string {
  return item.kind === 'series' ? `/series/${item.id}` : `/movies/${item.id}`
}

function heroMediaCopy(
  item: RecentItem,
  shows: Show[],
): { title: string; detail: string | null } {
  if (item.kind === 'series') {
    const seasonWord = item.title.match(/\b(?:season|series)\s*(\d{1,2})\b/i)
    let title = item.title
      .replace(/\b(?:season|series|seasons)\s*\d{1,2}\b/gi, ' ')
      .replace(/[._]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    title = title.replace(/[\s.\-_]+$/g, '') || item.title

    const show = shows.find((entry) => entry.id === item.id)
    if (seasonWord) {
      return { title, detail: `Season ${Number(seasonWord[1])}` }
    }
    if (show?.seasons.length === 1) {
      return { title, detail: `Season ${show.seasons[0].number}` }
    }
    if (show && show.seasons.length > 1) {
      const nums = show.seasons.map((season) => season.number).sort((a, b) => a - b)
      return { title, detail: `Seasons ${nums[0]}–${nums[nums.length - 1]}` }
    }
    return { title, detail: null }
  }

  const parenYear = item.title.match(/\((\d{4})\)/)
  const bareYear = item.title.match(/\b((?:19|20)\d{2})\b/)
  const year = parenYear?.[1] ?? bareYear?.[1] ?? null

  let title = item.title
  if (parenYear) {
    title = item.title.replace(/\s*\(\d{4}\)\s*/g, ' ').trim()
  } else if (year) {
    const yearIndex = item.title.search(/\b(?:19|20)\d{2}\b/)
    if (yearIndex > 0) {
      title = item.title.slice(0, yearIndex)
    }
  }

  title = title
    .replace(/[._]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/[\s.\-_]+$/g, '')
    .trim()

  return { title: title || item.title, detail: year }
}

export function HomePage() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [series, setSeries] = useState<Show[]>([])
  const [progress, setProgress] = useState<ProgressEntry[]>([])
  const [recent, setRecent] = useState<RecentItem[]>([])
  const [activeRecent, setActiveRecent] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [m, s, p, r] = await Promise.all([
          api.movies(),
          api.series(),
          api.progress(),
          api.recent(5),
        ])
        if (cancelled) return
        setMovies(m)
        setSeries(s)
        setProgress(p)
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
  const featuredCopy = featured ? heroMediaCopy(featured, series) : null

  return (
    <main className="page">
      <section className={`hero${featured?.poster ? ' has-poster' : ''}`}>
        {recent.map((item, index) =>
          item.poster ? (
            <div
              key={`${item.kind}-${item.id}`}
              className={`hero-backdrop${index === activeRecent ? ' active' : ''}`}
              aria-hidden={index !== activeRecent}
            >
              <img src={item.poster} alt="" />
            </div>
          ) : null,
        )}
        <div className="hero-scrim" aria-hidden />
        <div className="hero-content">
          <h1 className="hero-brand">Locflix</h1>
          {featured && featuredCopy ? (
            <>
              <Link className="hero-media" to={itemLink(featured)}>
                <h2 className="hero-title">{featuredCopy.title}</h2>
                {featuredCopy.detail ? <p className="hero-detail">{featuredCopy.detail}</p> : null}
              </Link>
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
                poster={item.poster}
                hasSubtitles={item.has_subtitles}
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
              hasSubtitles={movie.has_subtitles}
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
              hasSubtitles={show.has_subtitles}
            />
          ))
        )}
      </MediaRow>
    </main>
  )
}
