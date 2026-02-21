interface StatusBadgeProps {
  status: string
  message?: string | null
}

const statusConfig: Record<string, { bg: string; text: string; dot: string; border: string }> = {
  online: {
    bg: 'bg-emerald-500/8',
    text: 'text-emerald-400',
    dot: 'bg-emerald-400',
    border: 'border-emerald-500/20',
  },
  offline: {
    bg: 'bg-red-500/8',
    text: 'text-red-400',
    dot: 'bg-red-400',
    border: 'border-red-500/20',
  },
  provisioning: {
    bg: 'bg-amber-500/8',
    text: 'text-amber-400',
    dot: 'bg-amber-400',
    border: 'border-amber-500/20',
  },
  error: {
    bg: 'bg-orange-500/8',
    text: 'text-orange-400',
    dot: 'bg-orange-400',
    border: 'border-orange-500/20',
  },
}

export default function StatusBadge({ status, message }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.offline
  const showProgress = status === 'provisioning' && message
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.text} ${config.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full flex-none ${config.dot} ${status === 'provisioning' ? 'animate-pulse' : status === 'online' ? 'animate-pulse-glow' : ''}`} />
      {showProgress ? message : status}
    </span>
  )
}
