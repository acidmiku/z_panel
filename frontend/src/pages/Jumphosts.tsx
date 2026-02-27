import { useState, Fragment } from 'react'
import {
  useJumphosts, useCreateJumphost, useUpdateJumphost, useDeleteJumphost,
  useSyncJumphost, useReinstallJumphost, useJumphostLogs, type Jumphost,
} from '@/api/jumphosts'
import { useSSHKeys } from '@/api/ssh-keys'
import StatusBadge from '@/components/StatusBadge'
import ConfirmDialog from '@/components/ConfirmDialog'
import { formatRelativeTime } from '@/lib/utils'
import { toast } from '@/components/Toaster'
import { useMaskIPs } from '@/hooks/useMaskIPs'
import { Eye, EyeOff, Plus, Shield, RefreshCw, X, AlertTriangle } from 'lucide-react'

export default function Jumphosts() {
  const { data: jumphosts, isLoading } = useJumphosts()
  const { data: sshKeys } = useSSHKeys()
  const createJumphost = useCreateJumphost()
  const updateJumphost = useUpdateJumphost()
  const deleteJumphost = useDeleteJumphost()
  const syncJumphost = useSyncJumphost()
  const reinstallJumphost = useReinstallJumphost()

  const { masked, toggle: toggleMask, mask } = useMaskIPs()

  const [showAdd, setShowAdd] = useState(false)
  const [editJh, setEditJh] = useState<Jumphost | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [reinstallId, setReinstallId] = useState<string | null>(null)
  const [logsId, setLogsId] = useState<string | null>(null)
  const [expandedError, setExpandedError] = useState<string | null>(null)

  const [form, setForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '',
  })
  const [editForm, setEditForm] = useState({
    name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '',
  })

  const { data: logsData, isLoading: logsLoading, refetch: refetchLogs } = useJumphostLogs(logsId)

  const resetForm = () => setForm({ name: '', ip: '', ssh_port: 22, ssh_user: 'root', ssh_key_id: '' })

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
                      <td colSpan={6} className="!pt-0 !pb-2">
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
                <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">No jumphosts yet</td></tr>
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
