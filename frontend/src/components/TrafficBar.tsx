import { formatBytes } from '@/lib/utils'

interface TrafficBarProps {
  used: number
  limit: number | null
}

export default function TrafficBar({ used, limit }: TrafficBarProps) {
  if (!limit) {
    return <span className="text-sm text-muted-foreground">{formatBytes(used)} / Unlimited</span>
  }

  const pct = Math.min((used / limit) * 100, 100)
  const color = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : 'bg-primary'
  const glow = pct > 90 ? '' : pct > 70 ? '' : 'shadow-[0_0_8px_-2px_hsla(var(--glow-cyan),0.4)]'

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{formatBytes(used)}</span>
        <span>{formatBytes(limit)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
        <div
          className={`h-full rounded-full ${color} ${glow} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
