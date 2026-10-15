import { useEffect, useState } from 'react'
import { api } from '../api'
import type { MediaMetadata as MediaMetadataType } from '../types'

interface MediaMetadataProps {
  mediaId: string | null | undefined
  onSubtitlesChanged?: (hasSubtitles: boolean) => void
}

function joinParts(parts: Array<string | null | undefined>): string | null {
  const values = parts.filter((part): part is string => Boolean(part && part.trim()))
  return values.length > 0 ? values.join(' · ') : null
}

export function MediaMetadata({ mediaId }: MediaMetadataProps) {
  const [meta, setMeta] = useState<MediaMetadataType | null>(null)

  useEffect(() => {
    if (!mediaId) {
      setMeta(null)
      return
    }
    let cancelled = false
    api
      .mediaMetadata(mediaId)
      .then((data) => {
        if (!cancelled) setMeta(data)
      })
      .catch(() => {
        if (!cancelled) setMeta(null)
      })
    return () => {
      cancelled = true
    }
  }, [mediaId])

  if (!mediaId) return null
  if (!meta) {
    return <div className="media-meta-block muted">Loading details…</div>
  }

  const subtitleLabels = meta.has_subtitles ? meta.subtitles : []
  const badgeLabels = [
    ...(meta.quality ? [meta.quality] : []),
    ...meta.audio_languages,
  ]

  const videoLabel = joinParts([meta.video_codec, meta.video_profile, meta.frame_rate])
  const audioLabel = joinParts([
    meta.audio_languages.length > 0 ? meta.audio_languages.join(', ') : null,
    meta.audio_codec,
    meta.audio_channels,
    meta.sample_rate,
  ])

  const tableRows = [
    { label: 'Quality', value: meta.quality },
    { label: 'Duration', value: meta.duration_label },
    { label: 'Size', value: meta.size_label },
    { label: 'Container', value: meta.container },
    { label: 'Video', value: videoLabel },
    { label: 'Audio', value: audioLabel },
    { label: 'Bitrate', value: meta.bitrate_label },
    {
      label: 'Subtitles',
      value: subtitleLabels.length > 0 ? subtitleLabels.join(', ') : 'None',
    },
  ].filter((row) => Boolean(row.value))

  if (badgeLabels.length === 0 && tableRows.length === 0) return null

  return (
    <div className="media-meta-block">
      {badgeLabels.length > 0 ? (
        <div className="media-meta" aria-label="Media badges">
          {badgeLabels.map((label) => (
            <span key={label} className="meta-badge">
              {label}
            </span>
          ))}
        </div>
      ) : null}

      {tableRows.length > 0 ? (
        <table className="meta-table">
          <tbody>
            {tableRows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td>{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  )
}
