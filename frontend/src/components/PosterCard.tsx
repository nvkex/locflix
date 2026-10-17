import { useState } from 'react'
import { Link } from 'react-router-dom'
import { mediaAssetUrl } from '../api'

interface PosterCardProps {
  to: string
  title: string
  subtitle?: string
  poster?: string | null
  hasSubtitles?: boolean
}

export function PosterCard({ to, title, subtitle, poster, hasSubtitles = false }: PosterCardProps) {
  const [imgFailed, setImgFailed] = useState(false)
  const posterSrc = mediaAssetUrl(poster)
  const showImage = Boolean(posterSrc) && !imgFailed

  return (
    <Link to={to} className="poster-card">
      <div className={`poster${showImage ? ' has-image' : ''}`}>
        {showImage ? (
          <img src={posterSrc!} alt={title} loading="lazy" onError={() => setImgFailed(true)} />
        ) : (
          <span>{title}</span>
        )}
        {hasSubtitles ? (
          <span className="poster-cc" title="Subtitles available">
            CC
          </span>
        ) : null}
      </div>
      <div className="poster-caption">
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </Link>
  )
}
