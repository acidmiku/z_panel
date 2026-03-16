import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Monitor } from 'lucide-react'

function ClientNode({ selected }: NodeProps) {
  return (
    <div
      className={`relative px-5 py-3 rounded-xl glass transition-all duration-200 ${
        selected ? 'ring-2 ring-primary/50 glow-cyan-sm' : ''
      }`}
      style={{ minWidth: 140 }}
    >
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
          <Monitor className="w-4 h-4 text-primary" />
        </div>
        <div>
          <div className="text-xs font-semibold text-foreground">Client</div>
          <div className="text-[10px] text-muted-foreground">Your device</div>
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

export default memo(ClientNode)
