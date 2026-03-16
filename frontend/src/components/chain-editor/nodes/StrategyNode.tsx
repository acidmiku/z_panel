import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Shuffle, GitBranch, MousePointerClick } from 'lucide-react'

export interface StrategyNodeData {
  label: string
  strategyType: 'urltest' | 'fallback' | 'selector'
  testUrl?: string
  interval?: string
  tolerance?: number
  [key: string]: unknown
}

const STRATEGY_ICONS = {
  urltest: Shuffle,
  fallback: GitBranch,
  selector: MousePointerClick,
}

const STRATEGY_COLORS = {
  urltest: 'from-violet-500/20 to-violet-500/5 border-violet-500/40',
  fallback: 'from-amber-500/20 to-amber-500/5 border-amber-500/40',
  selector: 'from-teal-500/20 to-teal-500/5 border-teal-500/40',
}

function StrategyNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as StrategyNodeData
  const strategyType = d.strategyType || 'urltest'
  const Icon = STRATEGY_ICONS[strategyType] || Shuffle
  const colors = STRATEGY_COLORS[strategyType] || STRATEGY_COLORS.urltest

  return (
    <div
      className={`relative rounded-xl border-2 bg-gradient-to-br ${colors} backdrop-blur-lg transition-all duration-200 ${
        selected ? 'ring-2 ring-primary/40 glow-cyan-sm' : ''
      }`}
      style={{ minWidth: 150, clipPath: 'polygon(12% 0%, 88% 0%, 100% 50%, 88% 100%, 12% 100%, 0% 50%)' }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
        style={{ left: -2 }}
      />

      <div className="px-8 py-4 text-center">
        <div className="flex items-center justify-center gap-1.5 mb-0.5">
          <Icon className="w-3.5 h-3.5 text-foreground" />
          <span className="text-xs font-semibold text-foreground">{d.label || strategyType}</span>
        </div>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{strategyType}</span>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-primary !border-2 !border-background"
        style={{ right: -2 }}
      />
    </div>
  )
}

export default memo(StrategyNodeComponent)
