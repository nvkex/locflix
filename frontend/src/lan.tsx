import {
  createContext,
  useContext,
  useEffect,
  useEffectEvent,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, setRemoteSource, type RemoteSource } from './api'
import type { LanDevice, LanShareStatus, LanSource } from './types'

const DEVICE_ID_KEY = 'locflix.lan.device_id'
const REMOTE_KEY = 'locflix.lan.remote'

interface LanContextValue {
  share: LanShareStatus | null
  devices: LanDevice[]
  sources: LanSource[]
  remote: RemoteSource | null
  refreshing: boolean
  scanning: boolean
  connecting: boolean
  refreshShare: () => Promise<void>
  setShareEnabled: (enabled: boolean, name?: string) => Promise<void>
  grantOwnerConsent: (approved: boolean) => Promise<void>
  decideDeviceConsent: (sessionId: string, approve: boolean) => Promise<void>
  revokeDevice: (sessionId: string) => Promise<void>
  scanSources: () => Promise<void>
  connectSource: (source: LanSource) => Promise<void>
  disconnectRemote: () => void
  deviceName: string
}

const LanContext = createContext<LanContextValue | null>(null)

function readDeviceId(): string {
  try {
    const existing = localStorage.getItem(DEVICE_ID_KEY)
    if (existing) return existing
    const id = crypto.randomUUID()
    localStorage.setItem(DEVICE_ID_KEY, id)
    return id
  } catch {
    return `web-${Math.random().toString(36).slice(2)}`
  }
}

function readStoredRemote(): RemoteSource | null {
  try {
    const raw = localStorage.getItem(REMOTE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as RemoteSource
    if (parsed?.baseUrl && parsed?.token && parsed?.name) return parsed
  } catch {
    /* ignore */
  }
  return null
}

function defaultDeviceName(): string {
  if (typeof navigator !== 'undefined' && navigator.userAgent) {
    const ua = navigator.userAgent
    if (/Edg\//.test(ua)) return 'Edge browser'
    if (/Chrome\//.test(ua)) return 'Chrome browser'
    if (/Firefox\//.test(ua)) return 'Firefox browser'
    if (/Safari\//.test(ua)) return 'Safari browser'
  }
  return 'Locflix Leecher'
}

export function LanProvider({ children }: { children: ReactNode }) {
  const [share, setShare] = useState<LanShareStatus | null>(null)
  const [devices, setDevices] = useState<LanDevice[]>([])
  const [sources, setSources] = useState<LanSource[]>([])
  const [remote, setRemote] = useState<RemoteSource | null>(() => readStoredRemote())
  const [refreshing, setRefreshing] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const deviceId = useMemo(() => readDeviceId(), [])
  const deviceName = useMemo(() => defaultDeviceName(), [])

  const persistRemote = useEffectEvent((next: RemoteSource | null) => {
    setRemoteSource(next)
    setRemote(next)
    try {
      if (next) localStorage.setItem(REMOTE_KEY, JSON.stringify(next))
      else localStorage.removeItem(REMOTE_KEY)
    } catch {
      /* ignore */
    }
  })

  useEffect(() => {
    setRemoteSource(remote)
  }, [remote])

  const refreshShare = useEffectEvent(async () => {
    setRefreshing(true)
    try {
      const status = await api.lanStatus()
      setShare(status)
      if (status.share_enabled) {
        const [devs] = await Promise.all([api.lanDevices()])
        setDevices(devs)
      } else {
        setDevices([])
      }
    } catch {
      /* local API may be down */
    } finally {
      setRefreshing(false)
    }
  })

  useEffect(() => {
    void refreshShare()
    const id = window.setInterval(() => void refreshShare(), 2500)
    return () => window.clearInterval(id)
  }, [])

  async function setShareEnabled(enabled: boolean, name?: string) {
    const status = await api.lanShare(enabled, name)
    setShare(status)
    if (enabled) await refreshShare()
    else setDevices([])
  }

  async function grantOwnerConsent(approved: boolean) {
    const status = await api.lanOwnerConsent(approved)
    setShare(status)
    await refreshShare()
  }

  async function decideDeviceConsent(sessionId: string, approve: boolean) {
    await api.lanDecideConsent(sessionId, approve)
    await refreshShare()
  }

  async function revokeDevice(sessionId: string) {
    await api.lanRevokeDevice(sessionId)
    await refreshShare()
  }

  async function scanSources() {
    setScanning(true)
    try {
      const found = await api.lanDiscover()
      setSources(found)
    } finally {
      setScanning(false)
    }
  }

  async function connectSource(source: LanSource) {
    setConnecting(true)
    try {
      let result = await api.lanConnect({
        host: source.host,
        port: source.port,
        device_name: deviceName,
        device_id: deviceId,
      })

      const started = Date.now()
      while (result.status === 'pending' && Date.now() - started < 120_000) {
        await new Promise((r) => window.setTimeout(r, 1500))
        result = await api.lanConnectPoll(result.session_id, source.host, source.port)
      }

      if (result.status !== 'approved' || !result.token) {
        throw new Error(
          result.status === 'pending'
            ? 'Waiting for seeder consent timed out'
            : `Seeder ${result.status || 'rejected'} this device`,
        )
      }

      persistRemote({
        baseUrl: result.base_url || source.base_url,
        token: result.token,
        name: result.share_name || source.name,
        seederId: result.seeder_id || source.seeder_id,
        tokenHeader: result.token_header || 'X-Locflix-Lan-Token',
      })
    } finally {
      setConnecting(false)
    }
  }

  function disconnectRemote() {
    persistRemote(null)
  }

  const value: LanContextValue = {
    share,
    devices,
    sources,
    remote,
    refreshing,
    scanning,
    connecting,
    refreshShare,
    setShareEnabled,
    grantOwnerConsent,
    decideDeviceConsent,
    revokeDevice,
    scanSources,
    connectSource,
    disconnectRemote,
    deviceName,
  }

  return <LanContext.Provider value={value}>{children}</LanContext.Provider>
}

export function useLan(): LanContextValue {
  const ctx = useContext(LanContext)
  if (!ctx) throw new Error('useLan must be used within LanProvider')
  return ctx
}
