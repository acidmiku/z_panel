import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setToken } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      setToken(data.access_token, data.refresh_token)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
      {/* Floating gradient orbs */}
      <div className="login-orb login-orb-1" />
      <div className="login-orb login-orb-2" />
      <div className="login-orb login-orb-3" />

      {/* Subtle rotating ring */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div
          className="w-[700px] h-[700px] rounded-full border border-primary/[0.03]"
          style={{ animation: 'spin-slow 120s linear infinite' }}
        />
      </div>

      <div className="w-full max-w-sm relative z-10 animate-enter">
        <div className="glass-strong rounded-2xl p-8">
          {/* Monogram */}
          <div className="flex justify-center mb-8">
            <div className="w-14 h-14 rounded-xl flex items-center justify-center border border-primary/15 bg-gradient-to-br from-primary/15 to-transparent">
              <span className="font-display text-2xl font-extrabold text-gradient-cyan select-none">Z</span>
            </div>
          </div>

          <h1 className="text-2xl font-bold text-center mb-1">Z Panel</h1>
          <p className="text-sm text-muted-foreground text-center mb-8 tracking-wide">Infrastructure control</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground tracking-wide">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="input-glass"
                placeholder="admin"
                autoFocus
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground tracking-wide">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-glass"
                required
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-500/8 border border-red-500/15 px-3 py-2">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2.5 mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                  Signing in...
                </span>
              ) : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted-foreground/40 mt-6 tracking-widest uppercase">Secure tunnel management</p>
      </div>
    </div>
  )
}
