import { useState } from 'react'
import { Link } from 'react-router-dom'

interface PosterCardProps {
  to: string
  title: string
  subtitle?: string
  poster?: string | null
}

export function PosterCard({ to, title, subtitle, poster }: PosterCardProps) {
  const [imgFailed, setImgFailed] = useState(false)
  const showImage = Boolean(poster) && !imgFailed

  return (
    <Link to={to} className="poster-card">
      <div className={`poster${showImage ? ' has-image' : ''}`}>
        {showImage ? (
          <img src={poster!} alt={title} loading="lazy" onError={() => setImgFailed(true)} />
        ) : (
          <span>{title}</span>
        )}
      </div>
      <div className="poster-caption">
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </Link>
  )
}
