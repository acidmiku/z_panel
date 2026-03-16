import { useState, Fragment } from 'react'
import { useServers, useCreateServer, useBatchCreateServers, useUpdateServer, useDeleteServer, useSyncServer, useReinstallServer, useServerLogs, useInstallMtproxyServer, useUninstallMtproxyServer, Server } from '@/api/servers'
import { useSSHKeys } from '@/api/ssh-keys'
import { useCloudflareConfigs } from '@/api/cloudflare'
import StatusBadge from '@/components/StatusBadge'
import ConfirmDialog from '@/components/ConfirmDialog'
import { formatRelativeTime } from '@/lib/utils'
import { toast } from '@/components/Toaster'
import { useMaskIPs } from '@/hooks/useMaskIPs'
import TlsDomainInput from '@/components/TlsDomainInput'
import { Eye, EyeOff, Plus, Layers, Shield, RefreshCw, X, AlertTriangle, Send, Copy, Check } from 'lucide-react'

interface ServerFormData {
  name: string; ip: string; ssh_port: number; ssh_user: string
  ssh_key_id: string; cf_config_id: string
  hysteria2_port: number; reality_port: number
  reality_dest: string; reality_server_name: string
  subdomain_prefix: string
  install_mtproxy: boolean; mtproxy_port: number; mtproxy_tls_domain: string
}

function ServerFormFields({ f, setF, sshKeys, cfConfigs }: {
  f: ServerFormData
  setF: (v: ServerFormData) => void
  sshKeys?: { id: string; name: string }[]
  cfConfigs?: { id: string; name: string }[]
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
        <input value={f.name} onChange={e => setF({...f, name: e.target.value})} className="input-glass" required />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">IP Address</label>
        <input value={f.ip} onChange={e => setF({...f, ip: e.target.value})} className="input-glass font-mono" required />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Port</label>
        <input type="number" value={f.ssh_port} onChange={e => setF({...f, ssh_port: +e.target.value})} className="input-glass" />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH User</label>
        <input value={f.ssh_user} onChange={e => setF({...f, ssh_user: e.target.value})} className="input-glass font-mono" />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Key</label>
        <select value={f.ssh_key_id} onChange={e => setF({...f, ssh_key_id: e.target.value})} className="input-glass" required>
          <option value="">Select...</option>
          {sshKeys?.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Cloudflare Config</label>
        <select value={f.cf_config_id} onChange={e => setF({...f, cf_config_id: e.target.value})} className="input-glass" required>
          <option value="">Select...</option>
          {cfConfigs?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Subdomain Prefix</label>
        <input value={f.subdomain_prefix} onChange={e => setF({...f, subdomain_prefix: e.target.value})} className="input-glass font-mono" placeholder="node" />
        <p className="text-xs text-muted-foreground mt-0.5 opacity-60">{f.subdomain_prefix || 'node'}-xxxxx.domain.com</p>
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Hysteria2 Port</label>
        <input type="number" value={f.hysteria2_port} onChange={e => setF({...f, hysteria2_port: +e.target.value})} className="input-glass" />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality Port</label>
        <input type="number" value={f.reality_port} onChange={e => setF({...f, reality_port: +e.target.value})} className="input-glass" />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality Dest</label>
        <input value={f.reality_dest} onChange={e => setF({...f, reality_dest: e.target.value})} className="input-glass font-mono" />
      </div>
      <div>
        <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality SNI</label>
        <input value={f.reality_server_name} onChange={e => setF({...f, reality_server_name: e.target.value})} className="input-glass font-mono" />
      </div>
    </div>
  )
}

export default function Servers() {
  const { data: servers, isLoading } = useServers()
  const { data: sshKeys } = useSSHKeys()
  const { data: cfConfigs } = useCloudflareConfigs()
  const createServer = useCreateServer()
  const batchCreate = useBatchCreateServers()
  const updateServer = useUpdateServer()
  const deleteServer = useDeleteServer()
  const syncServer = useSyncServer()
  const reinstallServer = useReinstallServer()
  const installMtproxy = useInstallMtproxyServer()
  const uninstallMtproxy = useUninstallMtproxyServer()

  const { masked, toggle: toggleMask, mask } = useMaskIPs()

  const [showAdd, setShowAdd] = useState(false)
  const [showBatch, setShowBatch] = useState(false)
  const [editServer, setEditServer] = useState<Server | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [reinstallId, setReinstallId] = useState<string | null>(null)
  const [logsId, setLogsId] = useState<string | null>(null)
  const [expandedError, setExpandedError] = useState<string | null>(null)
  const [mtproxyId, setMtproxyId] = useState<string | null>(null)
  const [mtproxyForm, setMtproxyForm] = useState({ port: 443, tls_domain: 'www.google.com' })
  const [copiedLink, setCopiedLink] = useState<string | null>(null)
  const [uninstallMtproxyId, setUninstallMtproxyId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root',
    ssh_key_id: '', cf_config_id: '',
    hysteria2_port: 443, reality_port: 443,
    reality_dest: 'dl.google.com:443', reality_server_name: 'dl.google.com',
    subdomain_prefix: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })
  const [editForm, setEditForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root',
    ssh_key_id: '', cf_config_id: '',
    hysteria2_port: 443, reality_port: 443,
    reality_dest: '', reality_server_name: '',
    subdomain_prefix: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })
  const [batchForm, setBatchForm] = useState({
    ips_text: '', name_prefix: 'vps', ssh_port: 22, ssh_user: 'root',
    ssh_key_id: '', cf_config_id: '',
    hysteria2_port: 443, reality_port: 443,
    reality_dest: 'dl.google.com:443', reality_server_name: 'dl.google.com',
    subdomain_prefix: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })

  const { data: logsData, isLoading: logsLoading, refetch: refetchLogs } = useServerLogs(logsId)

  const resetForm = () => setForm({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root',
    ssh_key_id: '', cf_config_id: '',
    hysteria2_port: 443, reality_port: 443,
    reality_dest: 'dl.google.com:443', reality_server_name: 'dl.google.com',
    subdomain_prefix: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })

  const resetBatchForm = () => setBatchForm({
    ips_text: '', name_prefix: 'vps', ssh_port: 22, ssh_user: 'root',
    ssh_key_id: '', cf_config_id: '',
    hysteria2_port: 443, reality_port: 443,
    reality_dest: 'dl.google.com:443', reality_server_name: 'dl.google.com',
    subdomain_prefix: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })

  const parsedIps = batchForm.ips_text
    .split(/[\n,]+/)
    .map(s => s.trim())
    .filter(Boolean)

  const openEdit = (s: Server) => {
    setEditServer(s)
    setEditForm({
      name: s.name, ip: s.ip, ssh_port: s.ssh_port, ssh_user: s.ssh_user,
      ssh_key_id: s.ssh_key_id, cf_config_id: s.cf_config_id,
      hysteria2_port: s.hysteria2_port, reality_port: s.reality_port,
      reality_dest: s.reality_dest, reality_server_name: s.reality_server_name,
      subdomain_prefix: s.subdomain_prefix || '',
      install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
    })
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload = { ...form, subdomain_prefix: form.subdomain_prefix || null }
      await createServer.mutateAsync(payload)
      toast({ title: 'Server added', description: 'Provisioning started' })
      setShowAdd(false)
      resetForm()
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed to add server', variant: 'destructive' })
    }
  }

  const handleBatchCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (parsedIps.length === 0) return
    try {
      const { ips_text, ...rest } = batchForm
      await batchCreate.mutateAsync({ ...rest, subdomain_prefix: rest.subdomain_prefix || null, ips: parsedIps })
      toast({ title: `${parsedIps.length} servers added`, description: 'Provisioning started for all' })
      setShowBatch(false)
      resetBatchForm()
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Batch add failed', variant: 'destructive' })
    }
  }

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editServer) return
    try {
      await updateServer.mutateAsync({ id: editServer.id, ...editForm, subdomain_prefix: editForm.subdomain_prefix || null })
      toast({ title: 'Server updated', description: 'Sync config to apply changes on the remote server.' })
      setEditServer(null)
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed to update', variant: 'destructive' })
    }
  }

  const handleDelete = async (force = false) => {
    if (!deleteId) return
    try {
      await deleteServer.mutateAsync({ id: deleteId, force })
      toast({ title: 'Server deleted' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setDeleteId(null)
  }

  const handleReinstall = async () => {
    if (!reinstallId) return
    try {
      await reinstallServer.mutateAsync(reinstallId)
      toast({ title: 'Reinstall started', description: 'Server is being re-provisioned' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setReinstallId(null)
  }

  const handleInstallMtproxy = async () => {
    if (!mtproxyId) return
    try {
      await installMtproxy.mutateAsync({ id: mtproxyId, ...mtproxyForm })
      toast({ title: 'MTProxy install queued', description: 'Telemt will be installed in the background' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setMtproxyId(null)
  }

  const handleUninstallMtproxy = async () => {
    if (!uninstallMtproxyId) return
    try {
      await uninstallMtproxy.mutateAsync(uninstallMtproxyId)
      toast({ title: 'MTProxy uninstall queued' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setUninstallMtproxyId(null)
  }

  const copyLink = (link: string, id: string) => {
    navigator.clipboard.writeText(link)
    setCopiedLink(id)
    setTimeout(() => setCopiedLink(null), 2000)
  }

  const handleSync = async (id: string) => {
    try {
      await syncServer.mutateAsync(id)
      toast({ title: 'Config sync queued' })
    } catch {
      toast({ title: 'Error', description: 'Sync failed', variant: 'destructive' })
    }
  }

  const logsServer = servers?.find(s => s.id === logsId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Servers</h2>
          <p className="text-sm text-muted-foreground mt-1">Manage VPN infrastructure nodes</p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={toggleMask}
            className={`p-2.5 rounded-lg border transition-all ${masked ? 'border-primary/30 text-primary bg-primary/8' : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent'}`}
            title={masked ? 'Show IPs & hostnames' : 'Hide IPs & hostnames'}
          >
            {masked ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
          <button onClick={() => setShowBatch(true)} className="btn-ghost flex items-center gap-2">
            <Layers className="w-3.5 h-3.5" />
            Batch Add
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus className="w-3.5 h-3.5" />
            Add Server
          </button>
        </div>
      </div>

      {/* Add Server Modal */}
      {showAdd && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setShowAdd(false)} />
          <div className="modal-content max-w-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Add Server</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <ServerFormFields f={form} setF={setForm} sshKeys={sshKeys} cfConfigs={cfConfigs} />
              <div className="border-t border-border/40 pt-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.install_mtproxy} onChange={e => setForm({...form, install_mtproxy: e.target.checked})} className="rounded border-border" />
                  <Send className="w-3.5 h-3.5 text-sky-400" />
                  <span className="text-sm font-medium">Install MTProxy for Telegram</span>
                </label>
                {form.install_mtproxy && (
                  <div className="grid grid-cols-2 gap-3 mt-2 ml-6">
                    <div>
                      <label className="block text-xs font-medium mb-1 text-muted-foreground">Port</label>
                      <input type="number" value={form.mtproxy_port} onChange={e => setForm({...form, mtproxy_port: +e.target.value})} className="input-glass" />
                    </div>
                    <TlsDomainInput
                      value={form.mtproxy_tls_domain}
                      onChange={v => setForm({...form, mtproxy_tls_domain: v})}
                      ip={form.ip || null}
                    />
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-3 pt-3">
                <button type="button" onClick={() => setShowAdd(false)} className="btn-ghost">Cancel</button>
                <button type="submit" disabled={createServer.isPending} className="btn-primary">
                  {createServer.isPending ? 'Adding...' : 'Add Server'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Batch Add Modal */}
      {showBatch && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setShowBatch(false)} />
          <div className="modal-content max-w-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Batch Add Servers</h3>
            <form onSubmit={handleBatchCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">
                  IP Addresses <span className="font-normal opacity-60">(one per line or comma-separated)</span>
                </label>
                <textarea
                  value={batchForm.ips_text}
                  onChange={e => setBatchForm({...batchForm, ips_text: e.target.value})}
                  placeholder={"1.2.3.4\n5.6.7.8\n9.10.11.12"}
                  rows={5}
                  className="input-glass font-mono"
                  required
                />
                {parsedIps.length > 0 && (
                  <p className="text-xs text-primary mt-1 font-medium">{parsedIps.length} IP{parsedIps.length !== 1 ? 's' : ''} detected</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Name Prefix</label>
                  <input value={batchForm.name_prefix} onChange={e => setBatchForm({...batchForm, name_prefix: e.target.value})} className="input-glass" required />
                  <p className="text-xs text-muted-foreground mt-0.5">{batchForm.name_prefix}-1, {batchForm.name_prefix}-2, ...</p>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Subdomain Prefix</label>
                  <input value={batchForm.subdomain_prefix} onChange={e => setBatchForm({...batchForm, subdomain_prefix: e.target.value})} className="input-glass font-mono" placeholder="node" />
                  <p className="text-xs text-muted-foreground mt-0.5 opacity-60">{batchForm.subdomain_prefix || 'node'}-xxxxx.domain.com</p>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Port</label>
                  <input type="number" value={batchForm.ssh_port} onChange={e => setBatchForm({...batchForm, ssh_port: +e.target.value})} className="input-glass" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH User</label>
                  <input value={batchForm.ssh_user} onChange={e => setBatchForm({...batchForm, ssh_user: e.target.value})} className="input-glass font-mono" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Key</label>
                  <select value={batchForm.ssh_key_id} onChange={e => setBatchForm({...batchForm, ssh_key_id: e.target.value})} className="input-glass" required>
                    <option value="">Select...</option>
                    {sshKeys?.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Cloudflare Config</label>
                  <select value={batchForm.cf_config_id} onChange={e => setBatchForm({...batchForm, cf_config_id: e.target.value})} className="input-glass" required>
                    <option value="">Select...</option>
                    {cfConfigs?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Hysteria2 Port</label>
                  <input type="number" value={batchForm.hysteria2_port} onChange={e => setBatchForm({...batchForm, hysteria2_port: +e.target.value})} className="input-glass" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality Port</label>
                  <input type="number" value={batchForm.reality_port} onChange={e => setBatchForm({...batchForm, reality_port: +e.target.value})} className="input-glass" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality Dest</label>
                  <input value={batchForm.reality_dest} onChange={e => setBatchForm({...batchForm, reality_dest: e.target.value})} className="input-glass font-mono" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Reality SNI</label>
                  <input value={batchForm.reality_server_name} onChange={e => setBatchForm({...batchForm, reality_server_name: e.target.value})} className="input-glass font-mono" />
                </div>
              </div>
              <div className="border-t border-border/40 pt-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={batchForm.install_mtproxy} onChange={e => setBatchForm({...batchForm, install_mtproxy: e.target.checked})} className="rounded border-border" />
                  <Send className="w-3.5 h-3.5 text-sky-400" />
                  <span className="text-sm font-medium">Install MTProxy for Telegram</span>
                </label>
                {batchForm.install_mtproxy && (
                  <div className="grid grid-cols-2 gap-3 mt-2 ml-6">
                    <div>
                      <label className="block text-xs font-medium mb-1 text-muted-foreground">Port</label>
                      <input type="number" value={batchForm.mtproxy_port} onChange={e => setBatchForm({...batchForm, mtproxy_port: +e.target.value})} className="input-glass" />
                    </div>
                    <TlsDomainInput
                      value={batchForm.mtproxy_tls_domain}
                      onChange={v => setBatchForm({...batchForm, mtproxy_tls_domain: v})}
                      ip={parsedIps[0] || null}
                    />
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-3 pt-3">
                <button type="button" onClick={() => setShowBatch(false)} className="btn-ghost">Cancel</button>
                <button type="submit" disabled={batchCreate.isPending || parsedIps.length === 0} className="btn-primary">
                  {batchCreate.isPending ? 'Adding...' : `Add ${parsedIps.length} Server${parsedIps.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Server Modal */}
      {editServer && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setEditServer(null)} />
          <div className="modal-content max-w-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Edit Server</h3>
            <form onSubmit={handleEdit} className="space-y-3">
              <ServerFormFields f={editForm} setF={setEditForm} sshKeys={sshKeys} cfConfigs={cfConfigs} />
              <p className="text-xs text-muted-foreground">After saving, use Sync to push config changes or Reinstall to fully re-provision.</p>
              <div className="flex justify-end gap-3 pt-3">
                <button type="button" onClick={() => setEditServer(null)} className="btn-ghost">Cancel</button>
                <button type="submit" disabled={updateServer.isPending} className="btn-primary">
                  {updateServer.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading...</p>
      ) : (
        <div className="glass rounded-lg overflow-hidden">
          <table className="table-glass">
            <thead>
              <tr>
                <th>Name</th>
                <th>IP / FQDN</th>
                <th>Ports</th>
                <th>MTProxy</th>
                <th>Status</th>
                <th>Last Check</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {servers?.map(s => (
                <Fragment key={s.id}>
                  <tr>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium">{s.name}</span>
                        {s.hardened && (
                          <span title="Hardened"><Shield className="w-3 h-3 text-emerald-400/60" /></span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="font-mono text-xs">{mask(s.ip)}</div>
                      {s.fqdn && <div className="text-xs text-muted-foreground font-mono mt-0.5">{mask(s.fqdn)}</div>}
                    </td>
                    <td className="text-xs font-mono text-muted-foreground">
                      <div>Hy2: {s.hysteria2_port}/udp</div>
                      <div>VLESS: {s.reality_port}/tcp</div>
                    </td>
                    <td>
                      {s.mtproxy_enabled ? (
                        <div className="flex items-center gap-1.5">
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-400">
                            <Send className="w-3 h-3" />
                            :{s.mtproxy_port}
                          </span>
                          {s.mtproxy_link && (
                            <button
                              onClick={() => copyLink(s.mtproxy_link!, s.id)}
                              className="p-1 rounded hover:bg-accent transition-colors"
                              title="Copy tg:// link"
                            >
                              {copiedLink === s.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-muted-foreground" />}
                            </button>
                          )}
                          <button
                            onClick={() => setUninstallMtproxyId(s.id)}
                            className="p-1 rounded hover:bg-red-500/10 transition-colors"
                            title="Uninstall MTProxy"
                          >
                            <X className="w-3 h-3 text-red-400/60 hover:text-red-400" />
                          </button>
                        </div>
                      ) : s.status === 'online' ? (
                        <button
                          onClick={() => { setMtproxyId(s.id); setMtproxyForm({ port: 443, tls_domain: 'www.google.com' }) }}
                          className="text-xs px-2 py-0.5 rounded border border-sky-600/30 text-sky-400/70 hover:text-sky-400 hover:bg-sky-500/10 transition-all"
                        >
                          Install
                        </button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td><StatusBadge status={s.status} message={s.status_message} /></td>
                    <td className="text-muted-foreground text-xs">
                      {s.last_health_check ? formatRelativeTime(s.last_health_check) : '-'}
                    </td>
                    <td className="text-right space-x-1.5">
                      <button onClick={() => openEdit(s)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Edit</button>
                      <button onClick={() => setLogsId(s.id)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Logs</button>
                      <button onClick={() => handleSync(s.id)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Sync</button>
                      <button onClick={() => setReinstallId(s.id)} className="text-xs px-2.5 py-1 rounded-md border border-amber-600/40 text-amber-400 hover:bg-amber-500/10 transition-all">Reinstall</button>
                      <button onClick={() => setDeleteId(s.id)} className="text-xs px-2.5 py-1 rounded-md border border-red-600/40 text-red-400 hover:bg-red-500/10 transition-all">Delete</button>
                    </td>
                  </tr>
                  {(s.status === 'error' || s.status === 'offline') && s.status_message && (
                    <tr className="!border-b-0">
                      <td colSpan={7} className="!pt-0 !pb-2">
                        <div className="rounded-md bg-red-500/5 border border-red-500/15 px-3 py-2 mt-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <span className="text-xs font-semibold text-red-400">
                                {s.status === 'error' ? 'Error' : 'Offline'}:
                              </span>
                              <span className="text-xs text-red-300/70 ml-1 font-mono">
                                {expandedError === s.id
                                  ? s.status_message
                                  : s.status_message.length > 150
                                    ? s.status_message.slice(0, 150) + '...'
                                    : s.status_message
                                }
                              </span>
                            </div>
                            <div className="flex items-center gap-2 flex-none">
                              {s.status_message.length > 150 && (
                                <button
                                  onClick={() => setExpandedError(expandedError === s.id ? null : s.id)}
                                  className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap"
                                >
                                  {expandedError === s.id ? 'Less' : 'More'}
                                </button>
                              )}
                              <button
                                onClick={() => setLogsId(s.id)}
                                className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap underline underline-offset-2"
                              >
                                View Logs
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {servers?.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">No servers yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Logs Modal */}
      {logsId && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setLogsId(null)} />
          <div className="modal-content max-w-3xl flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border/40">
              <h3 className="text-lg font-semibold">
                Logs — <span className="text-primary">{logsServer?.name || 'Server'}</span>
              </h3>
              <div className="flex items-center gap-2">
                <button onClick={() => refetchLogs()} className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5">
                  <RefreshCw className="w-3 h-3" />
                  Refresh
                </button>
                <button onClick={() => setLogsId(null)} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-all">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {logsLoading ? (
                <p className="text-muted-foreground text-sm">Fetching logs via SSH...</p>
              ) : (
                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap break-all leading-relaxed">
                  {logsData?.logs || 'No logs available'}
                </pre>
              )}
            </div>
            {logsServer?.status_message && (
              <div className="border-t border-border/40 px-5 py-3 bg-red-500/5">
                <div className="text-xs font-semibold text-red-400 mb-1">Status Message</div>
                <pre className="text-xs font-mono text-red-300/70 whitespace-pre-wrap break-all">
                  {logsServer.status_message}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!reinstallId}
        title="Reinstall Server"
        description="This will stop sing-box, clean up the existing install, create a new DNS record, generate new Reality keys, and re-provision from scratch."
        confirmText="Reinstall"
        destructive={false}
        loading={reinstallServer.isPending}
        onConfirm={handleReinstall}
        onCancel={() => setReinstallId(null)}
      />

      {/* MTProxy Install Modal */}
      {mtproxyId && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setMtproxyId(null)} />
          <div className="modal-content max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-lg bg-sky-500/10 flex items-center justify-center flex-none">
                <Send className="w-4.5 h-4.5 text-sky-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Install MTProxy</h3>
                <p className="text-xs text-muted-foreground">Telemt with fake-TLS masking (maximum security)</p>
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Port</label>
                <input type="number" value={mtproxyForm.port} onChange={e => setMtproxyForm({...mtproxyForm, port: +e.target.value})} className="input-glass" />
                <p className="text-xs text-muted-foreground mt-0.5 opacity-60">443 recommended for censorship resistance</p>
              </div>
              <TlsDomainInput
                value={mtproxyForm.tls_domain}
                onChange={v => setMtproxyForm({...mtproxyForm, tls_domain: v})}
                ip={servers?.find(s => s.id === mtproxyId)?.ip || null}
              />
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <button onClick={() => setMtproxyId(null)} className="btn-ghost">Cancel</button>
              <button onClick={handleInstallMtproxy} disabled={installMtproxy.isPending} className="px-4 py-2 text-sm rounded-lg font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-all disabled:opacity-50">
                {installMtproxy.isPending ? 'Installing...' : 'Install'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!uninstallMtproxyId}
        title="Uninstall MTProxy"
        description="This will stop and remove telemt from the server. Existing tg:// links will stop working."
        confirmText="Uninstall"
        destructive
        loading={uninstallMtproxy.isPending}
        onConfirm={handleUninstallMtproxy}
        onCancel={() => setUninstallMtproxyId(null)}
      />

      {deleteId && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={deleteServer.isPending ? undefined : () => setDeleteId(null)} />
          <div className="modal-content max-w-md p-6">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center flex-none mt-0.5">
                <AlertTriangle className="w-4.5 h-4.5 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Delete Server</h3>
                <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
                  This will remove the server from the panel and delete its DNS record. This cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex justify-between mt-6">
              <button
                onClick={() => handleDelete(true)}
                disabled={deleteServer.isPending}
                className="text-xs px-3 py-1.5 rounded-md border border-red-600/30 text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50"
                title="Skip SSH cleanup — use when server is unreachable"
              >
                Force Delete
              </button>
              <div className="flex gap-3">
                <button onClick={() => setDeleteId(null)} className="btn-ghost" disabled={deleteServer.isPending}>
                  Cancel
                </button>
                <button
                  onClick={() => handleDelete(false)}
                  disabled={deleteServer.isPending}
                  className="px-4 py-2 text-sm rounded-lg font-semibold bg-red-600 hover:bg-red-500 text-white hover:shadow-[0_0_16px_-4px_rgba(239,68,68,0.35)] transition-all duration-200 disabled:opacity-50"
                >
                  {deleteServer.isPending ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                      Deleting...
                    </span>
                  ) : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
