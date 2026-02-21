import StatusBadge from './StatusBadge'
import Sparkline from './Sparkline'
import { formatRelativeTime } from '@/lib/utils'
import { useServerTrafficHistory } from '@/api/servers'
import type { Server } from '@/api/servers'
import { Shield } from 'lucide-react'

interface ServerCardProps {
  server: Server
  mask?: (value: string | null | undefined) => string
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  if (d > 0) return `${d}d ${h}h`
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatPct(used: number, total: number): string {
  if (total <= 0) return '0%'
  return Math.round((used / total) * 100) + '%'
}

function formatGiB(bytes: number): string {
  return (bytes / (1024 * 1024 * 1024)).toFixed(1)
}

export default function ServerCard({ server, mask }: ServerCardProps) {
  const { data: traffic } = useServerTrafficHistory(server.status === 'online' ? server.id : null)
  const m = mask || ((v: string | null | undefined) => v || '')

  const rates = traffic?.rates || []
  const sparkData = rates.map(r => r.rx_rate + r.tx_rate)

  const stats = server.system_stats

  return (
    <div className="glass rounded-lg p-4 hover:border-primary/25 transition-all duration-300 group">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-semibold text-sm group-hover:text-primary transition-colors truncate">{server.name}</h3>
          {server.hardened && (
            <span title="Hardened"><Shield className="w-3.5 h-3.5 text-emerald-400/60 flex-none" /></span>
          )}
        </div>
        <StatusBadge status={server.status} message={server.status_message} />
      </div>
      <p className="text-xs text-muted-foreground mt-1 font-mono truncate">{m(server.ip)}</p>
      {server.fqdn && (
        <p className="text-xs text-muted-foreground/60 mt-0.5 font-mono truncate">{m(server.fqdn)}</p>
      )}

      {/* Protocol ports */}
      <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400/60" />
          Hy2:{server.hysteria2_port}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-violet-400/60" />
          VLESS:{server.reality_port}
        </span>
      </div>

      {/* System stats */}
      {stats && (stats.uptime_seconds || stats.load_avg || stats.memory_total) && (
        <div className="mt-3 pt-3 border-t border-border/25 space-y-2">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {stats.uptime_seconds != null && (
              <span title="Uptime">Up {formatUptime(stats.uptime_seconds)}</span>
            )}
            {stats.load_avg && (
              <span title="Load average" className="font-mono text-foreground/60">
                {stats.load_avg[0].toFixed(2)}
              </span>
            )}
          </div>
          {/* Memory bar */}
          {stats.memory_total && stats.memory_used != null && (
            <div>
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>RAM</span>
                <span className="font-mono">{formatGiB(stats.memory_used)}/{formatGiB(stats.memory_total)}</span>
              </div>
              <div className="h-1 rounded-full bg-border/40 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary/50 transition-all duration-500"
                  style={{ width: formatPct(stats.memory_used, stats.memory_total) }}
                />
              </div>
            </div>
          )}
          {/* Disk bar */}
          {stats.disk_total && stats.disk_used != null && (
            <div>
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>Disk</span>
                <span className="font-mono">{formatGiB(stats.disk_used)}/{formatGiB(stats.disk_total)}</span>
              </div>
              <div className="h-1 rounded-full bg-border/40 overflow-hidden">
                <div
                  className="h-full rounded-full bg-violet-400/50 transition-all duration-500"
                  style={{ width: formatPct(stats.disk_used, stats.disk_total) }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Network traffic sparkline */}
      {sparkData.length >= 2 && (
        <div className="mt-3 pt-3 border-t border-border/25">
          <Sparkline data={sparkData} label="Network I/O" width={200} height={28} />
        </div>
      )}

      {/* Footer */}
      {server.last_health_check && (
        <p className="text-xs text-muted-foreground/60 mt-2.5">
          {formatRelativeTime(server.last_health_check)}
        </p>
      )}
      {server.status_message && (
        <p className="text-xs text-orange-400/70 mt-1 truncate">{server.status_message}</p>
      )}
    </div>
  )
}
