import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { PosterCard } from '../components/PosterCard'
import type { Movie, Show } from '../types'

export function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q') ?? ''
  const [movies, setMovies] = useState<Movie[]>([])
  const [series, setSeries] = useState<Show[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!q.trim()) {
      setMovies([])
      setSeries([])
      return
    }
    api
      .search(q)
      .then((res) => {
        setMovies(res.movies)
        setSeries(res.series)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Search failed'))
  }, [q])

  return (
    <main className="page">
      <h1 className="section-title">Search “{q}”</h1>
      {error && <p className="error">{error}</p>}
      <section className="section">
        <h2 className="section-title">Movies</h2>
        <div className="row">
          {movies.map((movie) => (
            <PosterCard
              key={movie.id}
              to={`/movies/${movie.id}`}
              title={movie.title}
              poster={movie.poster}
            />
          ))}
        </div>
        {movies.length === 0 && <p className="muted">No movie matches.</p>}
      </section>
      <section className="section">
        <h2 className="section-title">Series</h2>
        <div className="row">
          {series.map((show) => (
            <PosterCard
              key={show.id}
              to={`/series/${show.id}`}
              title={show.title}
              poster={show.poster}
            />
          ))}
        </div>
        {series.length === 0 && <p className="muted">No series matches.</p>}
      </section>
    </main>
  )
}
