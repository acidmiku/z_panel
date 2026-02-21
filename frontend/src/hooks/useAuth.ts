import { useState, useCallback } from 'react'

const TOKEN_KEY = 'vpn_panel_token'
const REFRESH_TOKEN_KEY = 'vpn_panel_refresh_token'

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY)
  )

  const setToken = useCallback((newToken: string | null, refreshToken?: string | null) => {
    if (newToken) {
      localStorage.setItem(TOKEN_KEY, newToken)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
    if (refreshToken !== undefined) {
      if (refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
      } else {
        localStorage.removeItem(REFRESH_TOKEN_KEY)
      }
    }
    setTokenState(newToken)
  }, [])

  const logout = useCallback(() => {
    setToken(null, null)
  }, [setToken])

  return { token, setToken, logout }
}
