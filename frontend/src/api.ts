import type {
  LibrarySummary,
  MediaMetadata,
  Movie,
  ProgressEntry,
  RecentItem,
  Show,
  SubtitlesResponse,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  library: () => request<LibrarySummary>('/api/library'),
  recent: (limit = 5) => request<RecentItem[]>(`/api/recent?limit=${limit}`),
  movies: () => request<Movie[]>('/api/movies'),
  movie: (id: string) => request<Movie>(`/api/movies/${id}`),
  series: () => request<Show[]>('/api/series'),
  show: (id: string) => request<Show>(`/api/series/${id}`),
  search: (q: string) =>
    request<{ movies: Movie[]; series: Show[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  scan: () => request<LibrarySummary>('/api/scan', { method: 'POST' }),
  fetchPosters: (force = false) =>
    request<{
      movies_with_posters: number
      series_with_posters: number
      tmdb_configured: boolean
    }>(`/api/posters/fetch?force=${force ? 'true' : 'false'}`, { method: 'POST' }),
  progress: () => request<ProgressEntry[]>('/api/progress'),
  getProgress: (id: string) => request<ProgressEntry>(`/api/progress/${id}`),
  putProgress: async (id: string, position_seconds: number, duration_seconds?: number) => {
    const res = await fetch(`/api/progress/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position_seconds, duration_seconds }),
    })
    if (res.status === 204) return null
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(detail || `Request failed: ${res.status}`)
    }
    return res.json() as Promise<ProgressEntry>
  },
  streamUrl: (id: string) => `/api/stream/${id}`,
  subtitles: (id: string) => request<SubtitlesResponse>(`/api/media/${id}/subtitles`),
  subtitleUrl: (mediaId: string, trackId: string) =>
    `/api/media/${mediaId}/subtitles/${trackId}`,
  mediaMetadata: (id: string) => request<MediaMetadata>(`/api/media/${id}/metadata`),
}
