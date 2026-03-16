import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Route } from 'lucide-react'

export interface RouteRule {
  id: string
  type: string
  value: string
  handleId: string
}

export interface RouteNodeData {
  label: string
  rules: RouteRule[]
  [key: string]: unknown
}

function RouteNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as RouteNodeData
  const rules = d.rules || []

  return (
    <div
      className={`relative rounded-xl glass border-2 border-purple-500/40 transition-all duration-200 ${
        selected ? 'ring-2 ring-primary/40 glow-cyan-sm' : ''
      }`}
      style={{ minWidth: 200 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
      />

      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <Route className="w-3.5 h-3.5 text-purple-400" />
          <span className="text-xs font-semibold text-foreground">{d.label || 'Route'}</span>
        </div>

        <div className="space-y-1">
          {rules.map((rule) => (
            <div key={rule.id} className="flex items-center justify-between text-[10px]">
              <span className="text-muted-foreground font-mono truncate max-w-[120px]">
                {rule.type}:{rule.value}
              </span>
              <Handle
                type="source"
                position={Position.Right}
                id={rule.handleId}
                className="!w-2.5 !h-2.5 !bg-purple-400 !border-2 !border-background"
                style={{ position: 'relative', right: 'auto', top: 'auto', transform: 'none' }}
              />
            </div>
          ))}

          {/* Final/default handle */}
          <div className="flex items-center justify-between text-[10px] pt-1 border-t border-border/40 mt-1">
            <span className="text-muted-foreground italic">final (default)</span>
            <Handle
              type="source"
              position={Position.Right}
              id="final"
              className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-background"
              style={{ position: 'relative', right: 'auto', top: 'auto', transform: 'none' }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default memo(RouteNodeComponent)
