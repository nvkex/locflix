import { useEffect, useState } from 'react'
import { api } from '../api'
import { PosterCard } from '../components/PosterCard'
import type { Show } from '../types'

export function SeriesPage() {
  const [series, setSeries] = useState<Show[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .series()
      .then(setSeries)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load series'))
  }, [])

  return (
    <main className="page">
      <h1 className="section-title">Series</h1>
      {error && <p className="error">{error}</p>}
      <div className="media-grid">
        {series.map((show) => (
          <PosterCard
            key={show.id}
            to={`/series/${show.id}`}
            title={show.title}
            subtitle={`${show.episode_count} episodes`}
            poster={show.poster}
          />
        ))}
      </div>
      {!error && series.length === 0 && <p className="muted">No series in the library yet.</p>}
    </main>
  )
}
