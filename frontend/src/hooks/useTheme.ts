import { useState, useCallback, useEffect } from 'react'

const THEME_KEY = 'vpn_panel_theme'

export type Theme = 'dark' | 'light'

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    const stored = localStorage.getItem(THEME_KEY)
    return (stored === 'light' || stored === 'dark') ? stored : 'dark'
  })

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'light') {
      root.classList.remove('dark')
      root.classList.add('light')
    } else {
      root.classList.remove('light')
      root.classList.add('dark')
    }
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  return { theme, toggleTheme }
}
