import { useEffect, useState } from 'react'
import { api } from '../api'
import { PosterCard } from '../components/PosterCard'
import type { Movie } from '../types'

export function MoviesPage() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .movies()
      .then(setMovies)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load movies'))
  }, [])

  return (
    <main className="page">
      <h1 className="section-title">Movies</h1>
      {error && <p className="error">{error}</p>}
      <div className="media-grid">
        {movies.map((movie) => (
          <PosterCard
            key={movie.id}
            to={`/movies/${movie.id}`}
            title={movie.title}
            poster={movie.poster}
            hasSubtitles={movie.has_subtitles}
          />
        ))}
      </div>
      {!error && movies.length === 0 && <p className="muted">No movies in the library yet.</p>}
    </main>
  )
}
