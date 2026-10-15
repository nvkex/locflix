export interface VideoFile {
  id: string
  filename: string
  path: string
  size: number
}

export interface Movie {
  id: string
  title: string
  path: string
  poster: string | null
  files: VideoFile[]
  default_file_id: string | null
  added_at: string | null
}

export interface Episode {
  id: string
  season: number
  episode: number
  title: string | null
  filename: string
  path: string
  size: number
}

export interface Season {
  number: number
  episodes: Episode[]
}

export interface Show {
  id: string
  title: string
  path: string
  poster: string | null
  seasons: Season[]
  episode_count: number
  added_at: string | null
}

export interface RecentItem {
  id: string
  title: string
  kind: 'movie' | 'series' | string
  added_at: string
  episode_count: number | null
  default_file_id: string | null
  poster: string | null
}

export interface LibrarySummary {
  movies: number
  series: number
  episodes: number
  last_scan_at: string | null
  movies_dir: string
  series_dir: string
}

export interface ProgressEntry {
  media_id: string
  position_seconds: number
  duration_seconds: number | null
  updated_at: string
  title: string | null
  kind: string | null
  poster: string | null
}

export interface SubtitleTrack {
  id: string
  label: string
  language: string | null
  source: string
  format: string | null
}

export interface SubtitlesResponse {
  media_id: string
  tracks: SubtitleTrack[]
  embedded_possible: boolean
}
