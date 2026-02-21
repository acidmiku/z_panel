import { useServers } from '@/api/servers'
import { useStats } from '@/api/stats'
import { formatBytes } from '@/lib/utils'
import ServerCard from '@/components/ServerCard'
import { useMaskIPs } from '@/hooks/useMaskIPs'
import { Server as ServerIcon, Users, Activity, Wifi, Eye, EyeOff } from 'lucide-react'

const statCards = [
  { key: 'servers', label: 'Servers', icon: ServerIcon },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'traffic', label: 'Traffic', icon: Activity },
  { key: 'online', label: 'Online', icon: Wifi },
]

export default function Dashboard() {
  const { data: servers, isLoading: serversLoading } = useServers()
  const { data: stats, isLoading: statsLoading } = useStats()
  const { masked, toggle: toggleMask, mask } = useMaskIPs()

  const getStatValue = (key: string) => {
    if (statsLoading) return '...'
    switch (key) {
      case 'servers': return stats?.total_servers ?? 0
      case 'users': return stats?.total_users ?? 0
      case 'traffic': return formatBytes(stats?.total_traffic_bytes ?? 0)
      case 'online': return `${stats?.online_servers ?? 0}/${stats?.total_servers ?? 0}`
      default: return 0
    }
  }

  const getStatSub = (key: string) => {
    if (!stats) return null
    switch (key) {
      case 'servers': return <span className="text-emerald-400">{stats.online_servers ?? 0} online</span>
      case 'users': return <span className="text-emerald-400">{stats.active_users ?? 0} active</span>
      default: return null
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
          <p className="text-sm text-muted-foreground mt-1">System status and server health</p>
        </div>
        <button
          onClick={toggleMask}
          className={`p-2.5 rounded-lg border transition-all ${masked ? 'border-primary/30 text-primary bg-primary/8' : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent'}`}
          title={masked ? 'Show IPs & hostnames' : 'Hide IPs & hostnames'}
        >
          {masked ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => {
          const Icon = card.icon
          return (
            <div
              key={card.key}
              className="glass rounded-lg p-5 group hover:border-primary/20 transition-all duration-300 animate-enter"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-medium text-muted-foreground tracking-wide">{card.label}</p>
                <Icon className="w-4 h-4 text-muted-foreground/40 group-hover:text-primary/50 transition-colors" />
              </div>
              <p className="text-2xl font-bold tracking-tight">{getStatValue(card.key)}</p>
              {getStatSub(card.key) && (
                <p className="text-xs mt-1.5">{getStatSub(card.key)}</p>
              )}
            </div>
          )
        })}
      </div>

      {/* Server Grid */}
      <div>
        <h3 className="text-lg font-semibold mb-4 tracking-tight">Servers</h3>
        {serversLoading ? (
          <p className="text-muted-foreground text-sm">Loading...</p>
        ) : servers?.length === 0 ? (
          <div className="glass rounded-lg p-12 text-center">
            <ServerIcon className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">No servers configured yet.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {servers?.map((server, i) => (
              <div key={server.id} className="animate-enter" style={{ animationDelay: `${(i + 4) * 50}ms` }}>
                <ServerCard server={server} mask={mask} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
