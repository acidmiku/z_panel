import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useUsers, useUser, useCreateUser, useUpdateUser, useDeleteUser, type VPNUser } from '@/api/users'
import { useServers, type Server } from '@/api/servers'
import TrafficBar from '@/components/TrafficBar'
import ConfirmDialog from '@/components/ConfirmDialog'
import { toast } from '@/components/Toaster'
import { UserPlus, ChevronRight, Pencil, Trash2, ExternalLink, Route, Users as UsersIcon } from 'lucide-react'

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function UserTrafficDetail({ userId, serverNameMap }: { userId: string; serverNameMap: Map<string, string> }) {
  const { data: user, isLoading } = useUser(userId)

  if (isLoading) {
    return (
      <tr className="bg-accent/30">
        <td colSpan={7} className="px-6 py-3 text-xs text-muted-foreground">Loading traffic data...</td>
      </tr>
    )
  }

  if (!user?.traffic_by_server || user.traffic_by_server.length === 0) {
    return (
      <tr className="bg-accent/30">
        <td colSpan={7} className="px-6 py-3 text-xs text-muted-foreground">No per-server traffic data yet</td>
      </tr>
    )
  }

  return (
    <tr className="bg-accent/30">
      <td colSpan={7} className="px-6 py-3">
        <div className="text-xs font-medium text-muted-foreground mb-2">Per-Server Traffic</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {user.traffic_by_server.map(t => (
            <div key={t.server_id} className="glass-subtle rounded-md px-3 py-2">
              <div className="text-xs font-medium truncate">{serverNameMap.get(t.server_id) || t.server_id.slice(0, 8)}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                <span className="text-emerald-400">&uarr;{formatBytes(t.bytes_up)}</span>
                {' / '}
                <span className="text-primary">&darr;{formatBytes(t.bytes_down)}</span>
              </div>
            </div>
          ))}
        </div>
      </td>
    </tr>
  )
}

export default function Users() {
  const { data: users, isLoading } = useUsers()
  const { data: servers } = useServers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()

  const [showAdd, setShowAdd] = useState(false)
  const [editUser, setEditUser] = useState<VPNUser | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [expandedUser, setExpandedUser] = useState<string | null>(null)
  const [form, setForm] = useState({
    username: '', traffic_limit_gb: 0, unlimited: true, expires_at: '', never_expires: true,
  })

  const openEdit = (u: VPNUser) => {
    setEditUser(u)
    setForm({
      username: u.username,
      traffic_limit_gb: u.traffic_limit_bytes ? Math.round(u.traffic_limit_bytes / (1024 * 1024 * 1024) * 100) / 100 : 0,
      unlimited: !u.traffic_limit_bytes,
      expires_at: u.expires_at ? u.expires_at.slice(0, 16) : '',
      never_expires: !u.expires_at,
    })
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createUser.mutateAsync({
        username: form.username,
        traffic_limit_bytes: form.unlimited ? null : Math.round(form.traffic_limit_gb * 1024 * 1024 * 1024),
        expires_at: form.never_expires ? null : form.expires_at || null,
      })
      toast({ title: 'User created', description: 'Config push triggered for all servers' })
      setShowAdd(false)
      setForm({ username: '', traffic_limit_gb: 0, unlimited: true, expires_at: '', never_expires: true })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editUser) return
    try {
      await updateUser.mutateAsync({
        id: editUser.id,
        username: form.username,
        traffic_limit_bytes: form.unlimited ? 0 : Math.round(form.traffic_limit_gb * 1024 * 1024 * 1024),
        expires_at: form.never_expires ? null : form.expires_at || null,
      })
      toast({ title: 'User updated' })
      setEditUser(null)
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const toggleEnabled = async (u: VPNUser) => {
    try {
      await updateUser.mutateAsync({ id: u.id, enabled: !u.enabled })
      toast({ title: u.enabled ? 'User disabled' : 'User enabled' })
    } catch { /* ignore */ }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteUser.mutateAsync(deleteId)
      toast({ title: 'User deleted' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setDeleteId(null)
  }

  const getUserStatus = (u: VPNUser) => {
    if (!u.enabled) return { label: 'Disabled', cls: 'text-red-400 bg-red-500/10 border-red-500/25' }
    if (u.expires_at && new Date(u.expires_at) < new Date()) return { label: 'Expired', cls: 'text-orange-400 bg-orange-500/10 border-orange-500/25' }
    if (u.traffic_limit_bytes && u.traffic_used_bytes >= u.traffic_limit_bytes) return { label: 'Over Limit', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/25' }
    return { label: 'Active', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25' }
  }

  const closeModal = () => { setShowAdd(false); setEditUser(null) }
  const isModalOpen = showAdd || !!editUser

  const serverNameMap = new Map((servers || []).map(s => [s.id, s.name]))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Users</h2>
          <p className="text-sm text-muted-foreground mt-1">Manage VPN user accounts</p>
        </div>
        <button onClick={() => { setShowAdd(true); setForm({ username: '', traffic_limit_gb: 0, unlimited: true, expires_at: '', never_expires: true }) }} className="btn-primary flex items-center gap-2">
          <UserPlus className="w-3.5 h-3.5" />
          Add User
        </button>
      </div>

      {/* User form modal - inlined to avoid focus bug */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-backdrop" onClick={closeModal} />
          <div className="modal-content max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">{showAdd ? 'Add User' : 'Edit User'}</h3>
            <form onSubmit={showAdd ? handleCreate : handleUpdate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Username</label>
                <input value={form.username} onChange={e => setForm({...form, username: e.target.value})} className="input-glass" required />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-muted-foreground">Traffic Limit</label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer text-muted-foreground hover:text-foreground transition-colors">
                    <input type="checkbox" checked={form.unlimited} onChange={e => setForm({...form, unlimited: e.target.checked})} className="rounded accent-primary" />
                    Unlimited
                  </label>
                </div>
                {!form.unlimited && (
                  <div className="flex gap-2 items-center">
                    <input type="number" value={form.traffic_limit_gb} onChange={e => setForm({...form, traffic_limit_gb: +e.target.value})} className="input-glass" min="0" step="0.1" />
                    <span className="text-xs text-muted-foreground whitespace-nowrap font-medium">GB</span>
                  </div>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-muted-foreground">Expiry Date</label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer text-muted-foreground hover:text-foreground transition-colors">
                    <input type="checkbox" checked={form.never_expires} onChange={e => setForm({...form, never_expires: e.target.checked})} className="rounded accent-primary" />
                    Never
                  </label>
                </div>
                {!form.never_expires && (
                  <input type="datetime-local" value={form.expires_at} onChange={e => setForm({...form, expires_at: e.target.value})} className="input-glass" />
                )}
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={closeModal} className="btn-ghost">Cancel</button>
                <button type="submit" className="btn-primary">
                  {showAdd ? 'Create' : 'Update'}
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
                <th></th>
                <th>Username</th>
                <th>Status</th>
                <th className="w-48">Traffic</th>
                <th>Expiry</th>
                <th>Created</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users?.map(u => {
                const status = getUserStatus(u)
                const isExpanded = expandedUser === u.id
                return (
                  <>
                    <tr key={u.id}>
                      <td className="w-8 px-2">
                        <button
                          onClick={() => setExpandedUser(isExpanded ? null : u.id)}
                          className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
                          title="Show per-server traffic"
                        >
                          <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                        </button>
                      </td>
                      <td className="font-medium">{u.username}</td>
                      <td>
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${status.cls}`}>
                          {status.label}
                        </span>
                      </td>
                      <td>
                        <TrafficBar used={u.traffic_used_bytes} limit={u.traffic_limit_bytes} />
                      </td>
                      <td className="text-xs text-muted-foreground">
                        {u.expires_at ? new Date(u.expires_at).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="text-xs text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="text-right space-x-1.5">
                        <button onClick={() => toggleEnabled(u)} className={`text-xs px-2.5 py-1 rounded-md border transition-all ${u.enabled ? 'border-amber-600/40 text-amber-400 hover:bg-amber-500/10' : 'border-emerald-600/40 text-emerald-400 hover:bg-emerald-500/10'}`}>
                          {u.enabled ? 'Disable' : 'Enable'}
                        </button>
                        <button onClick={() => openEdit(u)} className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent hover:border-primary/30 transition-all inline-flex items-center gap-1">
                          <Pencil className="w-3 h-3" />
                          Edit
                        </button>
                        <Link to={`/profiles/${u.id}`} className="text-xs px-2.5 py-1 rounded-md border border-primary/30 text-primary hover:bg-primary/10 transition-all inline-flex items-center gap-1">
                          <ExternalLink className="w-3 h-3" />
                          Profile
                        </Link>
                        <Link to={`/routing/${u.id}`} className="text-xs px-2.5 py-1 rounded-md border border-violet-500/30 text-violet-400 hover:bg-violet-500/10 transition-all inline-flex items-center gap-1">
                          <Route className="w-3 h-3" />
                          Routing
                        </Link>
                        <button onClick={() => setDeleteId(u.id)} className="text-xs px-2.5 py-1 rounded-md border border-red-600/40 text-red-400 hover:bg-red-500/10 transition-all inline-flex items-center gap-1">
                          <Trash2 className="w-3 h-3" />
                          Delete
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <UserTrafficDetail key={`${u.id}-detail`} userId={u.id} serverNameMap={serverNameMap} />
                    )}
                  </>
                )
              })}
              {users?.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                  <UsersIcon className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
                  No users yet
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteId}
        title="Delete User"
        description="This will remove the user and push updated configs to all servers."
        confirmText="Delete"
        destructive
        loading={deleteUser.isPending}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}
