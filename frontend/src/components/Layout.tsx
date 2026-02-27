import { Outlet, Link, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'
import { LayoutDashboard, Server, Users, Settings, Sun, Moon, LogOut, Network } from 'lucide-react'

const navGroups = [
  {
    items: [
      { path: '/', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/servers', label: 'Servers', icon: Server },
      { path: '/jumphosts', label: 'Jumphosts', icon: Network },
      { path: '/users', label: 'Users', icon: Users },
    ],
  },
  {
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

export default function Layout() {
  const location = useLocation()
  const { logout } = useAuth()
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="min-h-screen flex bg-mesh">
      {/* Sidebar */}
      <aside className="w-56 glass-subtle flex flex-col border-r border-border/40 z-10">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-border/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center border border-primary/15 bg-gradient-to-br from-primary/15 to-transparent">
              <span className="font-display text-sm font-extrabold text-gradient-cyan select-none">Z</span>
            </div>
            <span className="text-sm font-bold tracking-tight">Panel</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-6">
          {navGroups.map((group, gi) => (
            <div key={gi} className="space-y-0.5">
              {group.items.map(item => {
                const active = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                const Icon = item.icon
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`relative flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-all duration-200 ${
                      active
                        ? 'text-primary font-medium bg-primary/8 nav-active'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                    }`}
                  >
                    <Icon className="w-4 h-4" strokeWidth={active ? 2 : 1.5} />
                    {item.label}
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-border/40 flex items-center justify-between">
          <button
            onClick={toggleTheme}
            className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-accent/50 transition-all"
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button
            onClick={logout}
            className="p-2 text-muted-foreground hover:text-red-400 rounded-lg hover:bg-red-500/8 transition-all"
            title="Logout"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
