import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Server, Wifi, WifiOff } from 'lucide-react'

export interface ServerNodeData {
  label: string
  serverId?: string
  protocol: string
  status?: string
  ip?: string
  country?: string
  [key: string]: unknown
}

const PROTOCOL_COLORS: Record<string, string> = {
  ssh: 'border-green-500/60',
  shadowsocks: 'border-yellow-500/60',
  vless: 'border-blue-500/60',
  hysteria2: 'border-orange-500/60',
}

const PROTOCOL_BG: Record<string, string> = {
  ssh: 'bg-green-500/10 text-green-400',
  shadowsocks: 'bg-yellow-500/10 text-yellow-400',
  vless: 'bg-blue-500/10 text-blue-400',
  hysteria2: 'bg-orange-500/10 text-orange-400',
}

function ServerNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as ServerNodeData
  const proto = (d.protocol || 'vless').toLowerCase()
  const borderColor = PROTOCOL_COLORS[proto] || 'border-border'
  const isOnline = d.status === 'online'
  const protoBg = PROTOCOL_BG[proto] || 'bg-muted text-muted-foreground'

  const maskedIp = d.ip
    ? d.ip.replace(/\.\d+\.\d+$/, '.***.**')
    : ''

  return (
    <div
      className={`relative rounded-xl glass border-2 transition-all duration-200 ${borderColor} ${
        selected ? 'ring-2 ring-primary/40 glow-cyan-sm' : ''
      }`}
      style={{ minWidth: 170 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
      />

      <div className="px-4 py-3">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs font-semibold text-foreground truncate max-w-[100px]">
              {d.label || 'Server'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {d.status && (
              <div className={`w-2 h-2 rounded-full ${
                isOnline ? 'bg-green-400 animate-pulse-glow' : 'bg-red-400'
              }`} />
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${protoBg}`}>
            {proto.toUpperCase()}
          </span>
          {maskedIp && (
            <span className="text-[10px] text-muted-foreground font-mono">{maskedIp}</span>
          )}
          {d.country && (
            <span className="text-[10px]">{d.country}</span>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-primary !border-2 !border-background"
      />
    </div>
  )
}

export default memo(ServerNodeComponent)
