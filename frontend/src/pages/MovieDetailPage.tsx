import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { MediaMetadata } from '../components/MediaMetadata'
import type { Movie } from '../types'

function formatSize(bytes: number): string {
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

export function MovieDetailPage() {
  const { id } = useParams()
  const [movie, setMovie] = useState<Movie | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .movie(id)
      .then(setMovie)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load movie'))
  }, [id])

  if (error) {
    return (
      <main className="page">
        <p className="error">{error}</p>
      </main>
    )
  }

  if (!movie) {
    return (
      <main className="page">
        <p className="muted">Loading…</p>
      </main>
    )
  }

  const playId = movie.default_file_id ?? movie.files[0]?.id

  return (
    <main className="page">
      <div className="detail-layout">
        <aside className="detail-aside">
          <div className={`poster${movie.poster ? ' has-image' : ''}`} style={{ minHeight: 360 }}>
            {movie.poster ? (
              <img src={movie.poster} alt={movie.title} />
            ) : (
              <span>{movie.title}</span>
            )}
          </div>
          <MediaMetadata mediaId={playId ?? movie.id} />
        </aside>
        <section className="detail-panel glass">
          <h1>{movie.title}</h1>
          <p className="muted">{movie.files.length} video file{movie.files.length === 1 ? '' : 's'} in this folder</p>
          {playId && (
            <p style={{ marginTop: '1.25rem' }}>
              <Link className="btn btn-primary" to={`/watch/${playId}`}>
                Play
              </Link>
            </p>
          )}
          <ul className="file-list">
            {movie.files.map((file) => (
              <li key={file.id}>
                <div>
                  <div>{file.filename}</div>
                  <div className="muted" style={{ fontSize: '0.85rem' }}>
                    {formatSize(file.size)}
                  </div>
                </div>
                <Link className="btn" to={`/watch/${file.id}`}>
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
