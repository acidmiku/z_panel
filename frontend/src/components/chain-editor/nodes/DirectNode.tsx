import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Globe } from 'lucide-react'

function DirectNode({ selected }: NodeProps) {
  return (
    <div
      className={`relative px-5 py-3 rounded-xl glass transition-all duration-200 ${
        selected ? 'ring-2 ring-primary/50 glow-cyan-sm' : ''
      }`}
      style={{ minWidth: 130 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
      />
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Globe className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <div className="text-xs font-semibold text-foreground">Direct</div>
          <div className="text-[10px] text-muted-foreground">No proxy</div>
        </div>
      </div>
    </div>
  )
}

export default memo(DirectNode)
