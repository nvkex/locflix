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
    disconnectRemote,
  } = useLan()
  const [shareName, setShareName] = useState('')
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
                  <strong>{device.device_name}</strong>
                  <div className="muted">
                    {device.client_ip} · waiting · {formatWhen(device.created_at)}
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
                  <strong>{device.device_name}</strong>
                  <div className="muted">
                    {device.client_ip}
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
          Find Locflix seeders on your network and stream their library in this browser.
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
          <p className="muted">No sources yet. Scan while another device is sharing.</p>
        ) : (
          <ul className="lan-device-list">
            {sources.map((source) => (
              <li key={source.seeder_id}>
                <div>
                  <strong>{source.name}</strong>
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
      </section>
    </main>
  )
}
