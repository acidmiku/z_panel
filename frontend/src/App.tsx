import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Servers from './pages/Servers'
import Users from './pages/Users'
import Profiles from './pages/Profiles'
import Settings from './pages/Settings'
import { Toaster } from './components/Toaster'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="servers" element={<Servers />} />
          <Route path="users" element={<Users />} />
          <Route path="profiles/:userId" element={<Profiles />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  )
}
