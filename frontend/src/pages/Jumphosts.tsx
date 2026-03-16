import { useState, Fragment } from 'react'
import {
  useJumphosts, useCreateJumphost, useUpdateJumphost, useDeleteJumphost,
  useSyncJumphost, useReinstallJumphost, useJumphostLogs,
  useInstallMtproxyJumphost, useUninstallMtproxyJumphost, useSetupRelayJumphost, type Jumphost,
} from '@/api/jumphosts'
import { useServers } from '@/api/servers'
import { useSSHKeys } from '@/api/ssh-keys'
import StatusBadge from '@/components/StatusBadge'
import ConfirmDialog from '@/components/ConfirmDialog'
import TlsDomainInput from '@/components/TlsDomainInput'
import { formatRelativeTime } from '@/lib/utils'
import { toast } from '@/components/Toaster'
import { useMaskIPs } from '@/hooks/useMaskIPs'
import { Eye, EyeOff, Plus, Shield, RefreshCw, X, AlertTriangle, Send, Copy, Check, ArrowRight } from 'lucide-react'

export default function Jumphosts() {
  const { data: jumphosts, isLoading } = useJumphosts()
  const { data: sshKeys } = useSSHKeys()
  const createJumphost = useCreateJumphost()
  const updateJumphost = useUpdateJumphost()
  const deleteJumphost = useDeleteJumphost()
  const syncJumphost = useSyncJumphost()
  const reinstallJumphost = useReinstallJumphost()
  const installMtproxy = useInstallMtproxyJumphost()
  const uninstallMtproxy = useUninstallMtproxyJumphost()
  const setupRelay = useSetupRelayJumphost()
  const { data: servers } = useServers()

  const { masked, toggle: toggleMask, mask } = useMaskIPs()

  const [showAdd, setShowAdd] = useState(false)
  const [editJh, setEditJh] = useState<Jumphost | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [reinstallId, setReinstallId] = useState<string | null>(null)
  const [logsId, setLogsId] = useState<string | null>(null)
  const [expandedError, setExpandedError] = useState<string | null>(null)
  const [mtproxyId, setMtproxyId] = useState<string | null>(null)
  const [mtproxyForm, setMtproxyForm] = useState({ port: 443, tls_domain: 'www.google.com' })
  const [copiedLink, setCopiedLink] = useState<string | null>(null)
  const [uninstallMtproxyId, setUninstallMtproxyId] = useState<string | null>(null)
  const [relayId, setRelayId] = useState<string | null>(null)
  const [relayForm, setRelayForm] = useState({ server_id: '', port: 443, tls_domain: 'www.google.com' })

  const [form, setForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '',
    install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com',
  })
  const [editForm, setEditForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '',
  })

  const { data: logsData, isLoading: logsLoading, refetch: refetchLogs } = useJumphostLogs(logsId)

  const resetForm = () => setForm({ name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '', install_mtproxy: false, mtproxy_port: 443, mtproxy_tls_domain: 'www.google.com' })

  const openEdit = (j: Jumphost) => {
    setEditJh(j)
    setEditForm({
      name: j.name, ip: j.ip, ssh_port: j.ssh_port, ssh_user: j.ssh_user, ssh_key_id: j.ssh_key_id,
    })
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createJumphost.mutateAsync(form)
      toast({ title: 'Jumphost added', description: 'Provisioning started' })
      setShowAdd(false)
      resetForm()
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editJh) return
    try {
      await updateJumphost.mutateAsync({ id: editJh.id, ...editForm })
      toast({ title: 'Jumphost updated' })
      setEditJh(null)
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleDelete = async (force = false) => {
    if (!deleteId) return
    try {
      await deleteJumphost.mutateAsync({ id: deleteId, force })
      toast({ title: 'Jumphost deleted' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setDeleteId(null)
  }

  const handleReinstall = async () => {
    if (!reinstallId) return
    try {
      await reinstallJumphost.mutateAsync(reinstallId)
      toast({ title: 'Reinstall started' })
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

  const handleSetupRelay = async () => {
    if (!relayId || !relayForm.server_id) return
    try {
      await setupRelay.mutateAsync({ id: relayId, ...relayForm })
      toast({ title: 'Relay setup queued', description: 'TCP relay will be configured in the background' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setRelayId(null)
  }

  const mtproxyServers = servers?.filter(s => s.mtproxy_enabled) || []

  const copyLink = (link: string, id: string) => {
    navigator.clipboard.writeText(link)
    setCopiedLink(id)
    setTimeout(() => setCopiedLink(null), 2000)
  }

  const handleSync = async (id: string) => {
    try {
      await syncJumphost.mutateAsync(id)
      toast({ title: 'Config sync queued' })
    } catch {
      toast({ title: 'Error', description: 'Sync failed', variant: 'destructive' })
    }
  }

  const logsJh = jumphosts?.find(j => j.id === logsId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Jumphosts</h2>
          <p className="text-sm text-muted-foreground mt-1">Manage relay / first-hop servers</p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={toggleMask}
            className={`p-2.5 rounded-lg border transition-all ${masked ? 'border-primary/30 text-primary bg-primary/8' : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent'}`}
            title={masked ? 'Show IPs' : 'Hide IPs'}
          >
            {masked ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus className="w-3.5 h-3.5" />
            Add Jumphost
          </button>
        </div>
      </div>

      {/* Add Modal */}
      {showAdd && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setShowAdd(false)} />
          <div className="modal-content max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">Add Jumphost</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
                  <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="input-glass" required />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">IP Address</label>
                  <input value={form.ip} onChange={e => setForm({...form, ip: e.target.value})} className="input-glass font-mono" required />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Port</label>
                  <input type="number" value={form.ssh_port} onChange={e => setForm({...form, ssh_port: +e.target.value})} className="input-glass" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH User</label>
                  <input value={form.ssh_user} onChange={e => setForm({...form, ssh_user: e.target.value})} className="input-glass font-mono" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Key</label>
                  <select value={form.ssh_key_id} onChange={e => setForm({...form, ssh_key_id: e.target.value})} className="input-glass" required>
                    <option value="">Select...</option>
                    {sshKeys?.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
                  </select>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">Shadowsocks port and keys are auto-generated during provisioning.</p>
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
                <button type="submit" disabled={createJumphost.isPending} className="btn-primary">
                  {createJumphost.isPending ? 'Adding...' : 'Add Jumphost'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editJh && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setEditJh(null)} />
          <div className="modal-content max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">Edit Jumphost</h3>
            <form onSubmit={handleEdit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
                  <input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})} className="input-glass" required />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">IP Address</label>
                  <input value={editForm.ip} onChange={e => setEditForm({...editForm, ip: e.target.value})} className="input-glass font-mono" required />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Port</label>
                  <input type="number" value={editForm.ssh_port} onChange={e => setEditForm({...editForm, ssh_port: +e.target.value})} className="input-glass" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH User</label>
                  <input value={editForm.ssh_user} onChange={e => setEditForm({...editForm, ssh_user: e.target.value})} className="input-glass font-mono" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium mb-1 text-muted-foreground">SSH Key</label>
                  <select value={editForm.ssh_key_id} onChange={e => setEditForm({...editForm, ssh_key_id: e.target.value})} className="input-glass" required>
                    <option value="">Select...</option>
                    {sshKeys?.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-3">
                <button type="button" onClick={() => setEditJh(null)} className="btn-ghost">Cancel</button>
                <button type="submit" disabled={updateJumphost.isPending} className="btn-primary">
                  {updateJumphost.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading...</p>
      ) : (
        <div className="glass rounded-lg overflow-hidden">
          <table className="table-glass">
            <thead>
              <tr>
                <th>Name</th>
                <th>IP</th>
                <th>SS Port</th>
                <th>MTProxy</th>
                <th>Status</th>
                <th>Last Check</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jumphosts?.map(j => (
                <Fragment key={j.id}>
                  <tr>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium">{j.name}</span>
                        {j.hardened && (
                          <span title="Hardened"><Shield className="w-3 h-3 text-emerald-400/60" /></span>
                        )}
                      </div>
                    </td>
                    <td className="font-mono text-xs">{mask(j.ip)}</td>
                    <td className="text-xs font-mono text-muted-foreground">{j.shadowsocks_port || '—'}</td>
                    <td>
                      {j.mtproxy_enabled ? (
                        <div className="flex items-center gap-1.5">
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-400" title={j.mtproxy_relay_server_id ? 'Relay to server' : 'Direct'}>
                            {j.mtproxy_relay_server_id ? <ArrowRight className="w-3 h-3" /> : <Send className="w-3 h-3" />}
                            :{j.mtproxy_port}
                          </span>
                          {j.mtproxy_relay_server_id && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 font-medium">relay</span>
                          )}
                          {j.mtproxy_link && (
                            <button
                              onClick={() => copyLink(j.mtproxy_link!, j.id)}
                              className="p-1 rounded hover:bg-accent transition-colors"
                              title="Copy tg:// link"
                            >
                              {copiedLink === j.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-muted-foreground" />}
                            </button>
                          )}
                          <button
                            onClick={() => setUninstallMtproxyId(j.id)}
                            className="p-1 rounded hover:bg-red-500/10 transition-colors"
                            title={j.mtproxy_relay_server_id ? 'Remove relay' : 'Uninstall MTProxy'}
                          >
                            <X className="w-3 h-3 text-red-400/60 hover:text-red-400" />
                          </button>
                        </div>
                      ) : j.status === 'online' ? (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => { setMtproxyId(j.id); setMtproxyForm({ port: 443, tls_domain: 'www.google.com' }) }}
                            className="text-xs px-2 py-0.5 rounded border border-sky-600/30 text-sky-400/70 hover:text-sky-400 hover:bg-sky-500/10 transition-all"
                          >
                            Install
                          </button>
                          <button
                            onClick={() => { setRelayId(j.id); setRelayForm({ server_id: '', port: 443, tls_domain: 'www.google.com' }) }}
                            className="text-xs px-2 py-0.5 rounded border border-violet-600/30 text-violet-400/70 hover:text-violet-400 hover:bg-violet-500/10 transition-all"
                          >
                            Relay
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td><StatusBadge status={j.status} message={j.status_message} /></td>
                    <td className="text-muted-foreground text-xs">
                      {j.last_health_check ? formatRelativeTime(j.last_health_check) : '-'}
                    </td>
                    <td className="text-right space-x-1.5">
                      <button onClick={() => openEdit(j)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Edit</button>
                      <button onClick={() => setLogsId(j.id)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Logs</button>
                      <button onClick={() => handleSync(j.id)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all">Sync</button>
                      <button onClick={() => setReinstallId(j.id)} className="text-xs px-2.5 py-1 rounded-md border border-amber-600/40 text-amber-400 hover:bg-amber-500/10 transition-all">Reinstall</button>
                      <button onClick={() => setDeleteId(j.id)} className="text-xs px-2.5 py-1 rounded-md border border-red-600/40 text-red-400 hover:bg-red-500/10 transition-all">Delete</button>
                    </td>
                  </tr>
                  {(j.status === 'error' || j.status === 'offline') && j.status_message && (
                    <tr className="!border-b-0">
                      <td colSpan={7} className="!pt-0 !pb-2">
                        <div className="rounded-md bg-red-500/5 border border-red-500/15 px-3 py-2 mt-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <span className="text-xs font-semibold text-red-400">{j.status === 'error' ? 'Error' : 'Offline'}:</span>
                              <span className="text-xs text-red-300/70 ml-1 font-mono">
                                {expandedError === j.id ? j.status_message : j.status_message.length > 150 ? j.status_message.slice(0, 150) + '...' : j.status_message}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 flex-none">
                              {j.status_message.length > 150 && (
                                <button onClick={() => setExpandedError(expandedError === j.id ? null : j.id)} className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap">
                                  {expandedError === j.id ? 'Less' : 'More'}
                                </button>
                              )}
                              <button onClick={() => setLogsId(j.id)} className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap underline underline-offset-2">View Logs</button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {jumphosts?.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">No jumphosts yet</td></tr>
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
              <h3 className="text-lg font-semibold">Logs — <span className="text-primary">{logsJh?.name || 'Jumphost'}</span></h3>
              <div className="flex items-center gap-2">
                <button onClick={() => refetchLogs()} className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5">
                  <RefreshCw className="w-3 h-3" /> Refresh
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
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!reinstallId}
        title="Reinstall Jumphost"
        description="This will stop sing-box, clean up, generate new SS keys, and re-provision from scratch."
        confirmText="Reinstall"
        destructive={false}
        loading={reinstallJumphost.isPending}
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
                ip={jumphosts?.find(j => j.id === mtproxyId)?.ip || null}
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

      {/* Relay Setup Modal */}
      {relayId && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={() => setRelayId(null)} />
          <div className="modal-content max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-lg bg-violet-500/10 flex items-center justify-center flex-none">
                <ArrowRight className="w-4.5 h-4.5 text-violet-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Setup MTProxy Relay</h3>
                <p className="text-xs text-muted-foreground">TCP relay to a server's telemt — transparent to DPI</p>
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Relay to Server</label>
                <select
                  value={relayForm.server_id}
                  onChange={e => setRelayForm({...relayForm, server_id: e.target.value})}
                  className="input-glass"
                  required
                >
                  <option value="">Select a server with MTProxy...</option>
                  {mtproxyServers.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} — :{s.mtproxy_port} ({s.mtproxy_tls_domain})
                    </option>
                  ))}
                </select>
                {mtproxyServers.length === 0 && (
                  <p className="text-xs text-amber-400/70 mt-1">No servers have MTProxy installed. Install on a server first.</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Relay Port (on jumphost)</label>
                <input type="number" value={relayForm.port} onChange={e => setRelayForm({...relayForm, port: +e.target.value})} className="input-glass" />
                <p className="text-xs text-muted-foreground mt-0.5 opacity-60">Port users will connect to on the whitelisted jumphost</p>
              </div>
              <TlsDomainInput
                value={relayForm.tls_domain}
                onChange={v => setRelayForm({...relayForm, tls_domain: v})}
                ip={jumphosts?.find(j => j.id === relayId)?.ip || null}
              />
              <div className="rounded-lg bg-violet-500/5 border border-violet-500/15 px-3 py-2">
                <p className="text-xs text-violet-300/80 leading-relaxed">
                  Users connect to the <span className="font-semibold text-violet-300">jumphost IP</span> (whitelisted).
                  Traffic is transparently forwarded to the server's telemt.
                  DPI sees TLS to a whitelisted IP with a plausible domain.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <button onClick={() => setRelayId(null)} className="btn-ghost">Cancel</button>
              <button
                onClick={handleSetupRelay}
                disabled={setupRelay.isPending || !relayForm.server_id}
                className="px-4 py-2 text-sm rounded-lg font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-50"
              >
                {setupRelay.isPending ? 'Setting up...' : 'Setup Relay'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!uninstallMtproxyId}
        title="Uninstall MTProxy"
        description="This will stop and remove telemt from the jumphost. Existing tg:// links will stop working."
        confirmText="Uninstall"
        destructive
        loading={uninstallMtproxy.isPending}
        onConfirm={handleUninstallMtproxy}
        onCancel={() => setUninstallMtproxyId(null)}
      />

      {deleteId && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={deleteJumphost.isPending ? undefined : () => setDeleteId(null)} />
          <div className="modal-content max-w-md p-6">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center flex-none mt-0.5">
                <AlertTriangle className="w-4.5 h-4.5 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Delete Jumphost</h3>
                <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
                  This will remove the jumphost from the panel. Cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex justify-between mt-6">
              <button onClick={() => handleDelete(true)} disabled={deleteJumphost.isPending} className="text-xs px-3 py-1.5 rounded-md border border-red-600/30 text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50" title="Skip SSH cleanup">
                Force Delete
              </button>
              <div className="flex gap-3">
                <button onClick={() => setDeleteId(null)} className="btn-ghost" disabled={deleteJumphost.isPending}>Cancel</button>
                <button onClick={() => handleDelete(false)} disabled={deleteJumphost.isPending} className="px-4 py-2 text-sm rounded-lg font-semibold bg-red-600 hover:bg-red-500 text-white hover:shadow-[0_0_16px_-4px_rgba(239,68,68,0.35)] transition-all duration-200 disabled:opacity-50">
                  {deleteJumphost.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
