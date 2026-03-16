import { type DragEvent } from 'react'
import { Server, Globe, Shuffle, GitBranch, MousePointerClick, Route } from 'lucide-react'

interface PaletteItem {
  type: string
  label: string
  description: string
  icon: React.ElementType
  color: string
}

const PALETTE_GROUPS: { title: string; items: PaletteItem[] }[] = [
  {
    title: 'Servers',
    items: [
      { type: 'serverNode', label: 'Server', description: 'Proxy server', icon: Server, color: 'text-blue-400' },
    ],
  },
  {
    title: 'Strategy',
    items: [
      { type: 'strategyNode:urltest', label: 'URL Test', description: 'Auto-select fastest', icon: Shuffle, color: 'text-violet-400' },
      { type: 'strategyNode:fallback', label: 'Fallback', description: 'Use first available', icon: GitBranch, color: 'text-amber-400' },
      { type: 'strategyNode:selector', label: 'Selector', description: 'Manual selection', icon: MousePointerClick, color: 'text-teal-400' },
    ],
  },
  {
    title: 'Routing',
    items: [
      { type: 'routeNode', label: 'Route', description: 'Traffic rules', icon: Route, color: 'text-purple-400' },
    ],
  },
  {
    title: 'Terminal',
    items: [
      { type: 'directNode', label: 'Direct', description: 'No proxy', icon: Globe, color: 'text-emerald-400' },
    ],
  },
]

function onDragStart(event: DragEvent, nodeType: string) {
  event.dataTransfer.setData('application/reactflow', nodeType)
  event.dataTransfer.effectAllowed = 'move'
}

export default function NodePalette() {
  return (
    <div className="w-48 flex-shrink-0 glass-subtle border-r border-border/40 overflow-y-auto">
      <div className="px-3 py-3 border-b border-border/40">
        <h3 className="text-xs font-semibold text-foreground">Node Palette</h3>
        <p className="text-[10px] text-muted-foreground mt-0.5">Drag to canvas</p>
      </div>

      <div className="p-2 space-y-4">
        {PALETTE_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="px-1 mb-1.5">
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                {group.title}
              </span>
            </div>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <div
                    key={item.type}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-grab
                      bg-card/50 border border-border/40 hover:border-primary/30
                      hover:bg-primary/5 transition-all duration-150 active:cursor-grabbing"
                    draggable
                    onDragStart={(e) => onDragStart(e, item.type)}
                  >
                    <Icon className={`w-3.5 h-3.5 ${item.color}`} />
                    <div>
                      <div className="text-[11px] font-medium text-foreground leading-tight">{item.label}</div>
                      <div className="text-[9px] text-muted-foreground leading-tight">{item.description}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
