import { X } from 'lucide-react'
import type { Node } from '@xyflow/react'
import type { Server } from '@/api/servers'

interface Props {
  node: Node | null
  servers: Server[]
  onUpdate: (nodeId: string, data: Record<string, unknown>) => void
  onClose: () => void
}

export default function PropertiesPanel({ node, servers, onUpdate, onClose }: Props) {
  if (!node) return null

  const data = node.data as Record<string, unknown>
  const nodeType = node.type

  const update = (key: string, value: unknown) => {
    onUpdate(node.id, { ...data, [key]: value })
  }

  return (
    <div className="w-64 flex-shrink-0 glass-subtle border-l border-border/40 overflow-y-auto">
      <div className="px-3 py-3 border-b border-border/40 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground">Properties</h3>
        <button
          onClick={onClose}
          className="p-1 text-muted-foreground hover:text-foreground rounded transition-all"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-3 space-y-3">
        {/* Label (all node types) */}
        <div>
          <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Label</label>
          <input
            className="input-glass mt-1 !text-xs !py-1.5"
            value={(data.label as string) || ''}
            onChange={(e) => update('label', e.target.value)}
          />
        </div>

        {/* Server Node properties */}
        {nodeType === 'serverNode' && (
          <>
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Server</label>
              <select
                className="input-glass mt-1 !text-xs !py-1.5"
                value={(data.serverId as string) || ''}
                onChange={(e) => {
                  const srv = servers.find(s => s.id === e.target.value)
                  if (srv) {
                    update('serverId', srv.id)
                    onUpdate(node.id, {
                      ...data,
                      serverId: srv.id,
                      label: srv.name,
                      ip: srv.ip,
                      status: srv.status,
                      protocol: (data.protocol as string) || 'vless',
                    })
                  }
                }}
              >
                <option value="">Select server...</option>
                {servers.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.status})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Protocol</label>
              <select
                className="input-glass mt-1 !text-xs !py-1.5"
                value={(data.protocol as string) || 'vless'}
                onChange={(e) => update('protocol', e.target.value)}
              >
                <option value="ssh">SSH</option>
                <option value="shadowsocks">Shadowsocks</option>
                <option value="vless">VLESS-Reality</option>
                <option value="hysteria2">Hysteria2</option>
              </select>
            </div>

            {(data.protocol as string) === 'vless' && (
              <div>
                <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Transport</label>
                <select
                  className="input-glass mt-1 !text-xs !py-1.5"
                  value={(data.transport as string) || 'tcp'}
                  onChange={(e) => update('transport', e.target.value)}
                >
                  <option value="tcp">TCP</option>
                  <option value="ws">WebSocket</option>
                  <option value="grpc">gRPC</option>
                  <option value="h2">HTTP/2</option>
                </select>
              </div>
            )}

            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Port Override</label>
              <input
                className="input-glass mt-1 !text-xs !py-1.5"
                type="number"
                placeholder="Default"
                value={(data.portOverride as string) || ''}
                onChange={(e) => update('portOverride', e.target.value || null)}
              />
            </div>

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-primary w-3.5 h-3.5"
                  checked={!!data.mux}
                  onChange={(e) => update('mux', e.target.checked)}
                />
                <span className="text-[10px] text-foreground">MUX</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-primary w-3.5 h-3.5"
                  checked={!!data.padding}
                  onChange={(e) => update('padding', e.target.checked)}
                />
                <span className="text-[10px] text-foreground">Padding</span>
              </label>
            </div>
          </>
        )}

        {/* Strategy Node properties */}
        {nodeType === 'strategyNode' && (
          <>
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Strategy Type</label>
              <select
                className="input-glass mt-1 !text-xs !py-1.5"
                value={(data.strategyType as string) || 'urltest'}
                onChange={(e) => update('strategyType', e.target.value)}
              >
                <option value="urltest">URL Test</option>
                <option value="fallback">Fallback</option>
                <option value="selector">Selector</option>
              </select>
            </div>

            {((data.strategyType as string) || 'urltest') !== 'selector' && (
              <>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Test URL</label>
                  <input
                    className="input-glass mt-1 !text-xs !py-1.5"
                    value={(data.testUrl as string) || 'https://www.gstatic.com/generate_204'}
                    onChange={(e) => update('testUrl', e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Interval</label>
                  <input
                    className="input-glass mt-1 !text-xs !py-1.5"
                    value={(data.interval as string) || '5m'}
                    onChange={(e) => update('interval', e.target.value)}
                  />
                </div>
              </>
            )}

            {((data.strategyType as string) || 'urltest') === 'urltest' && (
              <div>
                <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Tolerance (ms)</label>
                <input
                  className="input-glass mt-1 !text-xs !py-1.5"
                  type="number"
                  value={(data.tolerance as number) ?? 50}
                  onChange={(e) => update('tolerance', parseInt(e.target.value) || 50)}
                />
              </div>
            )}
          </>
        )}

        {/* Route Node properties */}
        {nodeType === 'routeNode' && (
          <RouteRulesEditor
            rules={(data.rules as Array<{ id: string; type: string; value: string; handleId: string }>) || []}
            onChange={(rules) => update('rules', rules)}
          />
        )}
      </div>
    </div>
  )
}


function RouteRulesEditor({
  rules,
  onChange,
}: {
  rules: Array<{ id: string; type: string; value: string; handleId: string }>
  onChange: (rules: Array<{ id: string; type: string; value: string; handleId: string }>) => void
}) {
  const addRule = () => {
    const id = `rule-${Date.now()}`
    onChange([...rules, { id, type: 'geoip:ru', value: 'ru', handleId: id }])
  }

  const removeRule = (ruleId: string) => {
    onChange(rules.filter(r => r.id !== ruleId))
  }

  const updateRule = (ruleId: string, field: string, value: string) => {
    onChange(rules.map(r => r.id === ruleId ? { ...r, [field]: value } : r))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Rules</label>
        <button
          onClick={addRule}
          className="text-[10px] text-primary hover:text-primary/80 font-medium"
        >
          + Add Rule
        </button>
      </div>
      <div className="space-y-2">
        {rules.map((rule) => (
          <div key={rule.id} className="space-y-1 p-2 rounded-lg bg-card/50 border border-border/40">
            <select
              className="input-glass !text-[10px] !py-1"
              value={rule.type}
              onChange={(e) => updateRule(rule.id, 'type', e.target.value)}
            >
              <optgroup label="Geo Rules">
                <option value="geoip:ru">geoip:ru</option>
                <option value="geoip:cn">geoip:cn</option>
                <option value="geoip:ir">geoip:ir</option>
                <option value="geosite:category-ads">geosite:ads</option>
                <option value="geosite:cn">geosite:cn</option>
                <option value="geosite:ru">geosite:ru</option>
              </optgroup>
              <optgroup label="Custom">
                <option value="domain_suffix">domain_suffix</option>
                <option value="domain_keyword">domain_keyword</option>
                <option value="domain">domain</option>
                <option value="ip_cidr">ip_cidr</option>
              </optgroup>
            </select>
            {!rule.type.startsWith('geoip:') && !rule.type.startsWith('geosite:') && (
              <input
                className="input-glass !text-[10px] !py-1"
                placeholder="Values (comma separated)"
                value={rule.value}
                onChange={(e) => updateRule(rule.id, 'value', e.target.value)}
              />
            )}
            <button
              onClick={() => removeRule(rule.id)}
              className="text-[9px] text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
