import {
  createContext,
  useContext,
  useEffect,
  useEffectEvent,
  useState,
  type ReactNode,
} from 'react'

export type ThemeId = 'glass' | 'genui'

export const THEMES: { id: ThemeId; label: string; short: string }[] = [
  { id: 'glass', label: 'Glass UI', short: 'Glass' },
  { id: 'genui', label: 'GenUI', short: 'GenUI' },
]

const STORAGE_KEY = 'locflix.theme'

interface ThemeContextValue {
  theme: ThemeId
  setTheme: (theme: ThemeId) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStoredTheme(): ThemeId {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === 'glass' || raw === 'genui') return raw
  } catch {
    /* ignore */
  }
  return 'glass'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => readStoredTheme())

  const applyTheme = useEffectEvent((next: ThemeId) => {
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* ignore */
    }
  })

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  function setTheme(next: ThemeId) {
    setThemeState(next)
  }

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
