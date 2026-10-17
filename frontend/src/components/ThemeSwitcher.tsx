import { THEMES, useTheme, type ThemeId } from '../theme'

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="theme-switcher" role="group" aria-label="UI theme">
      <span className="theme-switcher-label">Theme</span>
      <div className="theme-switcher-track">
        {THEMES.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={theme === entry.id ? 'active' : ''}
            aria-pressed={theme === entry.id}
            title={entry.label}
            onClick={() => setTheme(entry.id as ThemeId)}
          >
            {entry.short}
          </button>
        ))}
      </div>
    </div>
  )
}
