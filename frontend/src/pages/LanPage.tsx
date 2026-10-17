import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLan } from '../lan'

function formatWhen(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function deviceLabel(device: { device_name: string; hostname?: string | null }): string {
  const name = (device.device_name || '').trim()
  const host = (device.hostname || '').trim()
  if (name) return name
  if (host) return host
  return 'Unknown device'
}

export function LanPage() {
  const {
    share,
    devices,
    sources,
    remote,
    scanning,
    connecting,
    setShareEnabled,
    grantOwnerConsent,
    decideDeviceConsent,
    revokeDevice,
    scanSources,
    connectSource,
    connectHost,
    disconnectRemote,
  } = useLan()
  const [shareName, setShareName] = useState('')
  const [manualHost, setManualHost] = useState('')
  const [manualPort, setManualPort] = useState('8787')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function onToggleShare() {
    setError(null)
    try {
      const enabling = !share?.share_enabled
      await setShareEnabled(enabling, shareName.trim() || undefined)
      if (!enabling) setShareName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update sharing')
    }
  }

  async function onConnect(seederId: string) {
    const source = sources.find((s) => s.seeder_id === seederId)
    if (!source) return
    setError(null)
    try {
      await connectSource(source)
      navigate('/')
      navigate(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect')
    }
  }

  async function onManualConnect() {
    setError(null)
    try {
      const port = Number(manualPort) || 8787
      await connectHost(manualHost, port)
      navigate('/')
      navigate(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect')
    }
  }

  const activeDevices = devices.filter((d) => d.status === 'approved')
  const pendingDevices = devices.filter((d) => d.status === 'pending')

  return (
    <main className="page lan-page">
      <header className="section-head">
        <h1 className="section-title">LAN streaming</h1>
      </header>
      {error ? <p className="error">{error}</p> : null}

      <section className="lan-panel glass">
        <div className="section-head">
          <h2 className="section-title">Seeder — share this library</h2>
        </div>
        <p className="muted">
          Turn this machine into a media source for other Locflix apps on the same Wi‑Fi.
        </p>
        <div className="lan-row">
          <label className="lan-field">
            <span>Display name</span>
            <input
              className="search-input"
              value={shareName || share?.share_name || ''}
              onChange={(e) => setShareName(e.target.value)}
              placeholder="e.g. Living Room PC"
              disabled={share?.share_enabled}
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={() => void onToggleShare()}>
            {share?.share_enabled ? 'Stop sharing' : 'Start sharing'}
          </button>
        </div>
        {share?.share_enabled ? (
          <div className="lan-meta">
            <span>
              Status:{' '}
              {share.owner_consented ? (
                <strong className="lan-ok">Live on LAN</strong>
              ) : (
                <strong>Waiting for consent</strong>
              )}
            </span>
            <span>
              Address: <code>{share.base_url}</code>
            </span>
            <span>
              Discovery:{' '}
              {share.beacon_running ? (
                <strong className="lan-ok">advertising UDP {share.discovery_port}</strong>
              ) : (
                <strong>{share.beacon_error || 'not advertising yet'}</strong>
              )}
            </span>
            {!share.owner_consented ? (
              <button type="button" className="btn" onClick={() => void grantOwnerConsent(true)}>
                Approve session consent
              </button>
            ) : (
              <button type="button" className="btn" onClick={() => void grantOwnerConsent(false)}>
                Revoke session consent
              </button>
            )}
          </div>
        ) : null}
      </section>

      <section className="lan-panel glass">
        <div className="section-head">
          <h2 className="section-title">Connected devices</h2>
        </div>
        <p className="muted">Devices currently connected or waiting to stream from this seeder.</p>
        {pendingDevices.length > 0 ? (
          <ul className="lan-device-list">
            {pendingDevices.map((device) => (
              <li key={device.session_id}>
                <div>
                  <div className="lan-device-name">{deviceLabel(device)}</div>
                  <div className="muted">
                    {device.client_ip}
                    {device.hostname ? ` · ${device.hostname}` : ''}
                    {' · waiting · '}
                    {formatWhen(device.created_at)}
                  </div>
                </div>
                <div className="lan-inline-actions">
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void decideDeviceConsent(device.session_id, false)}
                  >
                    Deny
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void decideDeviceConsent(device.session_id, true)}
                  >
                    Allow
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
        {activeDevices.length === 0 ? (
          <p className="muted">No devices streaming right now.</p>
        ) : (
          <ul className="lan-device-list">
            {activeDevices.map((device) => (
              <li key={device.session_id}>
                <div>
                  <div className="lan-device-name">{deviceLabel(device)}</div>
                  <div className="muted">
                    {device.client_ip}
                    {device.hostname && device.hostname !== device.device_name
                      ? ` · ${device.hostname}`
                      : ''}
                    {device.now_playing_title
                      ? ` · Playing ${device.now_playing_title}`
                      : ' · Idle'}
                    {' · '}
                    last seen {formatWhen(device.last_seen_at)}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn"
                  onClick={() => void revokeDevice(device.session_id)}
                >
                  Disconnect
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="lan-panel glass">
        <div className="section-head">
          <h2 className="section-title">Leecher — join a source</h2>
          <button
            type="button"
            className="btn"
            disabled={scanning || Boolean(remote)}
            onClick={() => void scanSources()}
          >
            {scanning ? 'Scanning…' : 'Scan LAN sources'}
          </button>
        </div>
        <p className="muted">
          Scans the Wi‑Fi subnet over HTTP (UDP broadcast is often blocked). Takes a few seconds.
        </p>
        {remote ? (
          <div className="lan-remote-active">
            <div>
              <strong>Streaming from {remote.name}</strong>
              <div className="muted">{remote.baseUrl}</div>
            </div>
            <button
              type="button"
              className="btn"
              onClick={() => {
                disconnectRemote()
                navigate(0)
              }}
            >
              Disconnect
            </button>
          </div>
        ) : sources.length === 0 ? (
          <p className="muted">
            No sources found yet. On the seeder, confirm sharing is live and discovery says
            advertising. You can also connect by IP below.
          </p>
        ) : (
          <ul className="lan-device-list">
            {sources.map((source) => (
              <li key={source.seeder_id}>
                <div>
                  <strong>
                    {source.name}
                    {source.is_self ? ' (this PC)' : ''}
                  </strong>
                  <div className="muted">{source.base_url}</div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={connecting}
                  onClick={() => void onConnect(source.seeder_id)}
                >
                  {connecting ? 'Connecting…' : 'Connect'}
                </button>
              </li>
            ))}
          </ul>
        )}
        {!remote ? (
          <div className="lan-row">
            <label className="lan-field">
              <span>Manual seeder IP / host</span>
              <input
                className="search-input"
                value={manualHost}
                onChange={(e) => setManualHost(e.target.value)}
                placeholder={share?.lan_ip || '192.168.0.4'}
              />
            </label>
            <label className="lan-field" style={{ flex: '0 0 7rem', minWidth: '7rem' }}>
              <span>Port</span>
              <input
                className="search-input"
                value={manualPort}
                onChange={(e) => setManualPort(e.target.value)}
                placeholder="8787"
              />
            </label>
            <button
              type="button"
              className="btn"
              disabled={connecting || !manualHost.trim()}
              onClick={() => void onManualConnect()}
            >
              Connect by IP
            </button>
          </div>
        ) : null}
      </section>
    </main>
  )
}
