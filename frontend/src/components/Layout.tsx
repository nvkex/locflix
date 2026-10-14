import { useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api'

export function Layout() {
  const [query, setQuery] = useState('')
  const [scanning, setScanning] = useState(false)
  const [fetchingPosters, setFetchingPosters] = useState(false)
  const navigate = useNavigate()

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
        </nav>
        <div className="nav-actions">
          <form onSubmit={onSearch}>
            <input
              className="search-input"
              placeholder="Search titles"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
          <button className="btn" type="button" onClick={onFetchPosters} disabled={fetchingPosters}>
            {fetchingPosters ? 'Posters…' : 'Fetch posters'}
          </button>
          <button className="btn" type="button" onClick={onScan} disabled={scanning}>
            {scanning ? 'Scanning…' : 'Rescan'}
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
