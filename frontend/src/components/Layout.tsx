import { useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useLan } from '../lan'
import { LanConsentModal } from './LanConsentModal'
import { ThemeSwitcher } from './ThemeSwitcher'

export function Layout() {
  const [query, setQuery] = useState('')
  const [scanning, setScanning] = useState(false)
  const [fetchingPosters, setFetchingPosters] = useState(false)
  const navigate = useNavigate()
  const { remote, share } = useLan()

  async function onScan() {
    setScanning(true)
    try {
      await api.scan()
      navigate(0)
    } finally {
      setScanning(false)
    }
  }

  async function onFetchPosters() {
    setFetchingPosters(true)
    try {
      await api.fetchPosters(false)
      navigate(0)
    } finally {
      setFetchingPosters(false)
    }
  }

  function onSearch(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`)
  }

  return (
    <div className="app-shell">
      <header className="nav glass">
        <Link to="/" className="brand">
          Locflix
        </Link>
        <nav className="nav-links">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/movies">Movies</NavLink>
          <NavLink to="/series">Series</NavLink>
          <NavLink to="/lan">LAN</NavLink>
        </nav>
        <div className="nav-actions">
          {remote ? (
            <div className="lan-header-badge" title={remote.baseUrl}>
              <span className="lan-header-kicker">Streaming from</span>
              <strong>{remote.name}</strong>
            </div>
          ) : share?.share_enabled && share.owner_consented ? (
            <div className="lan-header-badge seeder" title={share.base_url}>
              <span className="lan-header-kicker">Sharing as</span>
              <strong>{share.share_name}</strong>
            </div>
          ) : null}
          <ThemeSwitcher />
          <form onSubmit={onSearch}>
            <input
              className="search-input"
              placeholder="Search titles"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
          {!remote ? (
            <>
              <button
                className="btn"
                type="button"
                onClick={onFetchPosters}
                disabled={fetchingPosters}
              >
                {fetchingPosters ? 'Posters…' : 'Fetch posters'}
              </button>
              <button className="btn" type="button" onClick={onScan} disabled={scanning}>
                {scanning ? 'Scanning…' : 'Rescan'}
              </button>
            </>
          ) : (
            <Link className="btn" to="/lan">
              Sources
            </Link>
          )}
        </div>
      </header>
      <Outlet />
      <LanConsentModal />
    </div>
  )
}
