import type {
  LanConnectResult,
  LanDevice,
  LanShareStatus,
  LanSource,
  LibrarySummary,
  MediaMetadata,
  Movie,
  ProgressEntry,
  RecentItem,
  Show,
  SubtitleDownloadResult,
  SubtitlesResponse,
  TmdbInfo,
} from './types'

export interface RemoteSource {
  baseUrl: string
  token: string
  name: string
  seederId: string
  tokenHeader: string
}

let remoteSource: RemoteSource | null = null

export function setRemoteSource(source: RemoteSource | null) {
  remoteSource = source
}

export function getRemoteSource(): RemoteSource | null {
  return remoteSource
}

/** Rewrite relative /api poster URLs when browsing a remote seeder. */
export function mediaAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (!remoteSource) return path
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (!path.startsWith('/api/')) return path
  const url = new URL(path, remoteSource.baseUrl)
  url.searchParams.set('lan_token', remoteSource.token)
  return url.toString()
}

function resolveApiUrl(path: string): string {
  if (remoteSource && path.startsWith('/api/') && !path.startsWith('/api/lan/')) {
    return `${remoteSource.baseUrl}${path}`
  }
  return path
}

function withLanQuery(url: string): string {
  if (!remoteSource || !url.startsWith(remoteSource.baseUrl)) return url
  const parsed = new URL(url)
  parsed.searchParams.set('lan_token', remoteSource.token)
  return parsed.toString()
}

async function request<T>(path: string, init?: RequestInit, opts?: { local?: boolean }): Promise<T> {
  const local = Boolean(opts?.local || path.startsWith('/api/lan/'))
  const url = local ? path : resolveApiUrl(path)
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && init?.body != null) {
    headers.set('Content-Type', 'application/json')
  }
  if (!local && remoteSource && url.startsWith(remoteSource.baseUrl)) {
    headers.set(remoteSource.tokenHeader, remoteSource.token)
  }

  const res = await fetch(url, {
    ...init,
    headers,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health', undefined, { local: true }),
  library: () => request<LibrarySummary>('/api/library'),
  recent: (limit = 5) => request<RecentItem[]>(`/api/recent?limit=${limit}`),
  movies: () => request<Movie[]>('/api/movies'),
  movie: (id: string) => request<Movie>(`/api/movies/${id}`),
  series: () => request<Show[]>('/api/series'),
  show: (id: string) => request<Show>(`/api/series/${id}`),
  search: (q: string) =>
    request<{ movies: Movie[]; series: Show[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  scan: () => request<LibrarySummary>('/api/scan', { method: 'POST' }, { local: true }),
  fetchPosters: (force = false) =>
    request<{
      movies_with_posters: number
      series_with_posters: number
      tmdb_configured: boolean
    }>(
      `/api/posters/fetch?force=${force ? 'true' : 'false'}`,
      { method: 'POST' },
      { local: true },
    ),
  progress: () => request<ProgressEntry[]>('/api/progress', undefined, { local: true }),
  getProgress: (id: string) =>
    request<ProgressEntry>(`/api/progress/${id}`, undefined, { local: true }),
  putProgress: async (id: string, position_seconds: number, duration_seconds?: number) => {
    // Always persist resume position on the local leecher machine.
    const localRes = await fetch(`/api/progress/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position_seconds, duration_seconds }),
    })
    if (localRes.status === 204) return null
    if (!localRes.ok) {
      const detail = await localRes.text()
      throw new Error(detail || `Request failed: ${localRes.status}`)
    }
    return localRes.json() as Promise<ProgressEntry>
  },
  streamUrl: (id: string) => withLanQuery(resolveApiUrl(`/api/stream/${id}`)),
  subtitles: (id: string) => request<SubtitlesResponse>(`/api/media/${id}/subtitles`),
  subtitleUrl: (mediaId: string, trackId: string) =>
    withLanQuery(resolveApiUrl(`/api/media/${mediaId}/subtitles/${trackId}`)),
  mediaMetadata: (id: string) => request<MediaMetadata>(`/api/media/${id}/metadata`),
  downloadSubtitles: (id: string) =>
    request<SubtitleDownloadResult>(`/api/media/${id}/subtitles/download`, { method: 'POST' }),
  tmdbInfo: (kind: 'movie' | 'series', id: string) =>
    request<TmdbInfo>(kind === 'movie' ? `/api/movies/${id}/tmdb` : `/api/series/${id}/tmdb`),

  lanStatus: () => request<LanShareStatus>('/api/lan/status', undefined, { local: true }),
  lanShare: (enabled: boolean, name?: string) =>
    request<LanShareStatus>(
      '/api/lan/share',
      { method: 'POST', body: JSON.stringify({ enabled, name }) },
      { local: true },
    ),
  lanOwnerConsent: (approved: boolean) =>
    request<LanShareStatus>(
      '/api/lan/owner-consent',
      { method: 'POST', body: JSON.stringify({ approved }) },
      { local: true },
    ),
  lanDevices: () => request<LanDevice[]>('/api/lan/devices', undefined, { local: true }),
  lanPending: () => request<LanDevice[]>('/api/lan/consent/pending', undefined, { local: true }),
  lanDecideConsent: (sessionId: string, approve: boolean) =>
    request<LanDevice>(
      `/api/lan/consent/${sessionId}`,
      { method: 'POST', body: JSON.stringify({ approve }) },
      { local: true },
    ),
  lanRevokeDevice: (sessionId: string) =>
    request<{ status: string }>(`/api/lan/devices/${sessionId}`, { method: 'DELETE' }, { local: true }),
  lanDiscover: () => request<LanSource[]>('/api/lan/discover', { method: 'POST' }, { local: true }),
  lanSources: () => request<LanSource[]>('/api/lan/sources', undefined, { local: true }),
  lanConnect: (body: {
    host: string
    port: number
    device_name: string
    device_id: string
  }) =>
    request<LanConnectResult>(
      '/api/lan/connect',
      { method: 'POST', body: JSON.stringify(body) },
      { local: true },
    ),
  lanConnectPoll: (sessionId: string, host: string, port: number) =>
    request<LanConnectResult>(
      `/api/lan/connect/${sessionId}?host=${encodeURIComponent(host)}&port=${port}`,
      undefined,
      { local: true },
    ),
}
