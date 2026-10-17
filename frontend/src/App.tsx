import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { LanPage } from './pages/LanPage'
import { MovieDetailPage } from './pages/MovieDetailPage'
import { MoviesPage } from './pages/MoviesPage'
import { PlayerPage } from './pages/PlayerPage'
import { SearchPage } from './pages/SearchPage'
import { SeriesPage } from './pages/SeriesPage'
import { ShowDetailPage } from './pages/ShowDetailPage'
import { LanProvider } from './lan'

export default function App() {
  return (
    <LanProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="movies" element={<MoviesPage />} />
            <Route path="movies/:id" element={<MovieDetailPage />} />
            <Route path="series" element={<SeriesPage />} />
            <Route path="series/:id" element={<ShowDetailPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="lan" element={<LanPage />} />
            <Route path="watch/:id" element={<PlayerPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LanProvider>
  )
}
