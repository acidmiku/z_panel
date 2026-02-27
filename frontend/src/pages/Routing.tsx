import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useUser } from '@/api/users'
import { useJumphosts, type Jumphost } from '@/api/jumphosts'
import {
  useRoutingRules, useCreateRoutingRule, useDeleteRoutingRule,
  useRoutingConfig, useUpsertRoutingConfig, useGeoOptions,
  type RoutingRule, type GeoRuleEntry,
} from '@/api/routing'
import { toast } from '@/components/Toaster'
import { ArrowLeft, Plus, Trash2, Save } from 'lucide-react'

export default function Routing() {
  const { userId } = useParams<{ userId: string }>()
  const { data: user, isLoading: userLoading } = useUser(userId || '')
  const { data: jumphosts } = useJumphosts()
  const { data: rules } = useRoutingRules(userId || '')
  const { data: config } = useRoutingConfig(userId || '')
  const { data: geoOptions } = useGeoOptions()

  const createRule = useCreateRoutingRule(userId || '')
  const deleteRule = useDeleteRoutingRule(userId || '')
  const upsertConfig = useUpsertRoutingConfig(userId || '')

  // Config form state
  const [selectedJumphost, setSelectedJumphost] = useState<string>('')
  const [selectedProtocol, setSelectedProtocol] = useState<'ss' | 'ssh'>('ss')
  const [selectedGeoRules, setSelectedGeoRules] = useState<GeoRuleEntry[]>([])

  // Rule form state
  const [showAddRule, setShowAddRule] = useState(false)
  const [ruleForm, setRuleForm] = useState({
    domain_pattern: '',
    match_type: 'domain-suffix' as string,
    action: 'proxy' as string,
    order: 0,
  })

  // Sync config form with loaded data
  useEffect(() => {
    if (config) {
      setSelectedJumphost(config.jumphost_id || '')
      setSelectedProtocol(config.jumphost_protocol || 'ss')
      setSelectedGeoRules(config.geo_rules || [])
    }
  }, [config])

  const isGeoEnabled = (geoId: string) => selectedGeoRules.some(r => r.id === geoId)
  const getGeoAction = (geoId: string) => selectedGeoRules.find(r => r.id === geoId)?.action

  const handleSaveConfig = async () => {
    try {
      await upsertConfig.mutateAsync({
        jumphost_id: selectedJumphost || null,
        jumphost_protocol: selectedProtocol,
        geo_rules: selectedGeoRules.length > 0 ? selectedGeoRules : null,
      })
      toast({ title: 'Routing config saved' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createRule.mutateAsync(ruleForm)
      toast({ title: 'Rule added' })
      setShowAddRule(false)
      setRuleForm({ domain_pattern: '', match_type: 'domain-suffix', action: 'proxy', order: 0 })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleDeleteRule = async (id: string) => {
    try {
      await deleteRule.mutateAsync(id)
      toast({ title: 'Rule deleted' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const toggleGeoRule = (geoId: string, defaultAction: string) => {
    setSelectedGeoRules(prev =>
      prev.some(r => r.id === geoId)
        ? prev.filter(r => r.id !== geoId)
        : [...prev, { id: geoId, action: defaultAction as GeoRuleEntry['action'] }]
    )
  }

  const setGeoAction = (geoId: string, action: GeoRuleEntry['action']) => {
    setSelectedGeoRules(prev =>
      prev.map(r => r.id === geoId ? { ...r, action } : r)
    )
  }

  if (userLoading) return <p className="text-muted-foreground text-sm">Loading...</p>
  if (!user) return <p className="text-red-400">User not found</p>

  const onlineJumphosts = jumphosts?.filter(j => j.status === 'online') || []

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link to="/users" className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-all">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Routing: <span className="text-primary">{user.username}</span></h2>
          <p className="text-sm text-muted-foreground mt-1">Jumphost, geo rules, and custom routing</p>
        </div>
      </div>

      {/* Jumphost Selection */}
      <div className="glass rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-semibold">Jumphost</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">Jumphost Server</label>
            <select
              value={selectedJumphost}
              onChange={e => setSelectedJumphost(e.target.value)}
              className="input-glass"
            >
              <option value="">None (direct connection)</option>
              {onlineJumphosts.map(j => (
                <option key={j.id} value={j.id}>{j.name} ({j.ip})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">Protocol</label>
            <div className="flex gap-2">
              {(['ss', 'ssh'] as const).map(p => (
                <label
                  key={p}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-all ${
                    selectedProtocol === p
                      ? 'glass text-primary font-medium glow-cyan-sm'
                      : 'border border-border hover:bg-accent/60 text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <input type="radio" name="jh_protocol" value={p} checked={selectedProtocol === p} onChange={() => setSelectedProtocol(p)} className="sr-only" />
                  {p === 'ss' ? 'Shadowsocks' : 'SSH Tunnel'}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Geo Rules */}
      <div className="glass rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-semibold">Geo Rule Providers</h3>
        <p className="text-xs text-muted-foreground">Enable geo-based rule sets from MetaCubeX. Each enabled ruleset routes matching traffic to the selected action.</p>
        <div className="space-y-1.5">
          {geoOptions?.map(opt => {
            const enabled = isGeoEnabled(opt.id)
            const action = getGeoAction(opt.id)
            return (
              <div
                key={opt.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  enabled
                    ? 'glass border-primary/30'
                    : 'border border-border hover:bg-accent/40'
                }`}
              >
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => toggleGeoRule(opt.id, opt.default_action)}
                  className="rounded accent-primary shrink-0"
                />
                <span className={`text-sm flex-1 min-w-0 truncate ${enabled ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                  {opt.label}
                </span>
                {enabled && (
                  <select
                    value={action}
                    onChange={e => setGeoAction(opt.id, e.target.value as GeoRuleEntry['action'])}
                    className="text-xs rounded-md border border-border bg-background px-2 py-1 shrink-0"
                  >
                    <option value="DIRECT">DIRECT</option>
                    <option value="Proxy">Proxy</option>
                    <option value="REJECT">REJECT</option>
                  </select>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Save Config */}
      <div>
        <button
          onClick={handleSaveConfig}
          disabled={upsertConfig.isPending}
          className="btn-primary px-6 py-2.5 inline-flex items-center gap-2"
        >
          <Save className="w-4 h-4" />
          {upsertConfig.isPending ? 'Saving...' : 'Save Routing Config'}
        </button>
      </div>

      {/* Custom Routing Rules */}
      <div className="glass rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Custom Rules</h3>
          <button onClick={() => setShowAddRule(true)} className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5">
            <Plus className="w-3 h-3" /> Add Rule
          </button>
        </div>

        {showAddRule && (
          <form onSubmit={handleAddRule} className="border border-border/40 rounded-lg p-4 space-y-3 bg-accent/20">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Domain Pattern</label>
                <input
                  value={ruleForm.domain_pattern}
                  onChange={e => setRuleForm({...ruleForm, domain_pattern: e.target.value})}
                  className="input-glass font-mono"
                  placeholder="google.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Match Type</label>
                <select value={ruleForm.match_type} onChange={e => setRuleForm({...ruleForm, match_type: e.target.value})} className="input-glass">
                  <option value="domain">domain</option>
                  <option value="domain-suffix">domain-suffix</option>
                  <option value="domain-keyword">domain-keyword</option>
                  <option value="domain-regex">domain-regex</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Action</label>
                <select value={ruleForm.action} onChange={e => setRuleForm({...ruleForm, action: e.target.value})} className="input-glass">
                  <option value="proxy">Proxy</option>
                  <option value="direct">Direct</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Order</label>
                <input type="number" value={ruleForm.order} onChange={e => setRuleForm({...ruleForm, order: +e.target.value})} className="input-glass" />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowAddRule(false)} className="btn-ghost text-xs">Cancel</button>
              <button type="submit" disabled={createRule.isPending} className="btn-primary text-xs">
                {createRule.isPending ? 'Adding...' : 'Add'}
              </button>
            </div>
          </form>
        )}

        {rules && rules.length > 0 ? (
          <div className="space-y-1">
            {rules.map(rule => (
              <div key={rule.id} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-accent/30 transition-colors group">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`text-xs px-2 py-0.5 rounded border ${
                    rule.action === 'proxy'
                      ? 'text-primary border-primary/30 bg-primary/8'
                      : 'text-emerald-400 border-emerald-500/30 bg-emerald-500/8'
                  }`}>
                    {rule.action}
                  </span>
                  <span className="text-xs text-muted-foreground">{rule.match_type}</span>
                  <code className="text-xs font-mono truncate">{rule.domain_pattern}</code>
                  {!rule.user_id && (
                    <span className="text-xs text-amber-400/60 border border-amber-500/20 rounded px-1.5">global</span>
                  )}
                </div>
                <button
                  onClick={() => handleDeleteRule(rule.id)}
                  className="text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all p-1"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No custom rules yet. Default rules: GEOIP LAN/CN direct, everything else via Proxy.</p>
        )}
      </div>
    </div>
  )
}
