import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useUser } from '@/api/users'
import { useServers } from '@/api/servers'
import { useRoutingConfig } from '@/api/routing'
import { useJumphosts } from '@/api/jumphosts'
import { downloadClashProfile } from '@/api/profiles'
import { toast } from '@/components/Toaster'
import { Copy, Download, Link2, Fingerprint, Route } from 'lucide-react'

export default function Profiles() {
  const { userId } = useParams<{ userId: string }>()
  const { data: user, isLoading: userLoading } = useUser(userId || '')
  const { data: servers } = useServers()
  const { data: routingConfig } = useRoutingConfig(userId || '')
  const { data: jumphosts } = useJumphosts()
  const [strategy, setStrategy] = useState('url-test')
  const [selectedServers, setSelectedServers] = useState<string[]>([])
  const [selectAll, setSelectAll] = useState(true)
  const [downloading, setDownloading] = useState(false)

  const onlineServers = servers?.filter(s => s.status === 'online') || []

  const toggleServer = (id: string) => {
    setSelectAll(false)
    setSelectedServers(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleDownload = async () => {
    if (!userId) return
    setDownloading(true)
    try {
      await downloadClashProfile(userId, strategy, selectAll ? 'all' : selectedServers)
      toast({ title: 'Profile downloaded' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Download failed', variant: 'destructive' })
    } finally {
      setDownloading(false)
    }
  }

  if (userLoading) return <p className="text-muted-foreground text-sm">Loading...</p>
  if (!user) return <p className="text-red-400">User not found</p>

  const subUrl = user.sub_token
    ? `${window.location.origin}/api/profiles/sub/${user.sub_token}`
    : null

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Profile: <span className="text-primary">{user.username}</span></h2>
        <p className="text-sm text-muted-foreground mt-1">Subscription links and credentials</p>
      </div>

      {/* Credentials */}
      <div className="glass rounded-lg p-5 space-y-3">
        <div className="flex items-center gap-2.5 mb-1">
          <Fingerprint className="w-4 h-4 text-primary/60" />
          <span className="text-sm font-semibold">Credentials</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground tracking-wide">UUID</span>
          <code className="text-xs font-mono bg-secondary/50 px-2 py-1 rounded">{user.uuid}</code>
        </div>
        <div className="border-t border-border/30" />
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground tracking-wide">Hysteria2 Password</span>
          <code className="text-xs font-mono bg-secondary/50 px-2 py-1 rounded">{user.hysteria2_password}</code>
        </div>
      </div>

      {/* Routing Summary */}
      <div className="glass rounded-lg p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Route className="w-4 h-4 text-violet-400/60" />
            <span className="text-sm font-semibold">Routing</span>
          </div>
          <Link to={`/routing/${userId}`} className="text-xs text-primary hover:underline">Configure</Link>
        </div>
        {routingConfig ? (
          <div className="space-y-2 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Jumphost</span>
              <span className="font-medium text-foreground">
                {routingConfig.jumphost_id
                  ? jumphosts?.find(j => j.id === routingConfig.jumphost_id)?.name || 'Unknown'
                  : 'None'}
                {routingConfig.jumphost_id && ` (${routingConfig.jumphost_protocol.toUpperCase()})`}
              </span>
            </div>
            {routingConfig.geo_rules && routingConfig.geo_rules.length > 0 && (
              <div className="flex items-center justify-between">
                <span>Geo rules</span>
                <span className="font-medium text-foreground">{routingConfig.geo_rules.length} active</span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No routing config set. <Link to={`/routing/${userId}`} className="text-primary hover:underline">Set up routing</Link></p>
        )}
      </div>

      {/* Subscription URLs */}
      {subUrl && (
        <div className="glass rounded-lg p-5 space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link2 className="w-3.5 h-3.5 text-primary/60" />
              <label className="text-sm font-semibold">Clash Meta Subscription</label>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              Paste into Clash Meta / Mihomo / Stash as a subscription. Configs auto-refresh.
            </p>
            <div className="flex gap-2">
              <input
                readOnly
                value={subUrl}
                className="input-glass flex-1 font-mono text-xs"
              />
              <button
                onClick={() => { navigator.clipboard.writeText(subUrl); toast({ title: 'Copied!' }) }}
                className="btn-ghost whitespace-nowrap text-xs px-3 inline-flex items-center gap-1.5"
              >
                <Copy className="w-3 h-3" />
                Copy
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Append <code className="bg-secondary/50 px-1.5 py-0.5 rounded text-primary">?strategy=fallback</code> or <code className="bg-secondary/50 px-1.5 py-0.5 rounded text-primary">?strategy=load-balance</code> to change type.
            </p>
          </div>
          <div className="border-t border-border/30" />
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link2 className="w-3.5 h-3.5 text-primary/60" />
              <label className="text-sm font-semibold">v2rayN / v2rayNG Subscription</label>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              Paste into v2rayN, v2rayNG, Nekoray, or Hiddify as a subscription URL.
            </p>
            <div className="flex gap-2">
              <input
                readOnly
                value={`${subUrl}/v2ray`}
                className="input-glass flex-1 font-mono text-xs"
              />
              <button
                onClick={() => { navigator.clipboard.writeText(`${subUrl}/v2ray`); toast({ title: 'Copied!' }) }}
                className="btn-ghost whitespace-nowrap text-xs px-3 inline-flex items-center gap-1.5"
              >
                <Copy className="w-3 h-3" />
                Copy
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Strategy Selection */}
      <div>
        <label className="block text-sm font-semibold mb-3">Proxy Group Strategy</label>
        <div className="flex gap-2">
          {['url-test', 'fallback', 'load-balance'].map(s => (
            <label key={s} className={`flex items-center gap-2 px-4 py-2.5 rounded-lg cursor-pointer text-sm transition-all duration-200 ${strategy === s ? 'glass text-primary font-medium glow-cyan-sm' : 'border border-border hover:bg-accent/60 text-muted-foreground hover:text-foreground'}`}>
              <input type="radio" name="strategy" value={s} checked={strategy === s} onChange={() => setStrategy(s)} className="sr-only" />
              {s}
            </label>
          ))}
        </div>
      </div>

      {/* Server Selection */}
      <div>
        <label className="block text-sm font-semibold mb-3">Servers</label>
        <label className="flex items-center gap-2 mb-2 text-sm cursor-pointer text-muted-foreground hover:text-foreground transition-colors">
          <input type="checkbox" checked={selectAll} onChange={e => { setSelectAll(e.target.checked); setSelectedServers([]) }} className="rounded accent-primary" />
          All online servers
        </label>
        {!selectAll && (
          <div className="space-y-1 ml-6">
            {onlineServers.length === 0 ? (
              <p className="text-xs text-muted-foreground">No online servers available</p>
            ) : (
              onlineServers.map(s => (
                <label key={s.id} className="flex items-center gap-2 text-sm cursor-pointer text-muted-foreground hover:text-foreground transition-colors">
                  <input type="checkbox" checked={selectedServers.includes(s.id)} onChange={() => toggleServer(s.id)} className="rounded accent-primary" />
                  {s.name} <span className="font-mono text-xs opacity-60">({s.fqdn || s.ip})</span>
                </label>
              ))
            )}
          </div>
        )}
      </div>

      {/* Download */}
      <div>
        <button
          onClick={handleDownload}
          disabled={downloading || (!selectAll && selectedServers.length === 0)}
          className="btn-primary px-6 py-2.5 inline-flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          {downloading ? 'Downloading...' : 'Download Clash Meta Profile'}
        </button>
      </div>
    </div>
  )
}
