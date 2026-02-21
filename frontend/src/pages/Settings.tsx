import { useState } from 'react'
import { useCloudflareConfigs, useCreateCloudflareConfig, useDeleteCloudflareConfig } from '@/api/cloudflare'
import { useSSHKeys, useCreateSSHKey, useDeleteSSHKey } from '@/api/ssh-keys'
import { changePassword } from '@/api/auth'
import ConfirmDialog from '@/components/ConfirmDialog'
import { toast } from '@/components/Toaster'
import { Cloud, KeyRound, Lock, Plus, Trash2 } from 'lucide-react'

export default function Settings() {
  const { data: cfConfigs } = useCloudflareConfigs()
  const createCf = useCreateCloudflareConfig()
  const deleteCf = useDeleteCloudflareConfig()
  const { data: sshKeys } = useSSHKeys()
  const createKey = useCreateSSHKey()
  const deleteKey = useDeleteSSHKey()

  const [cfForm, setCfForm] = useState({ name: '', api_token: '', zone_id: '', base_domain: '' })
  const [keyForm, setKeyForm] = useState({ name: '', private_key_path: '' })
  const [pwForm, setPwForm] = useState({ current: '', new1: '', new2: '' })
  const [deleteTarget, setDeleteTarget] = useState<{ type: 'cf' | 'ssh'; id: string } | null>(null)
  const [showCfForm, setShowCfForm] = useState(false)
  const [showKeyForm, setShowKeyForm] = useState(false)

  const handleCreateCf = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createCf.mutateAsync(cfForm)
      toast({ title: 'Cloudflare config added' })
      setCfForm({ name: '', api_token: '', zone_id: '', base_domain: '' })
      setShowCfForm(false)
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createKey.mutateAsync(keyForm)
      toast({ title: 'SSH key registered' })
      setKeyForm({ name: '', private_key_path: '' })
      setShowKeyForm(false)
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      if (deleteTarget.type === 'cf') await deleteCf.mutateAsync(deleteTarget.id)
      else await deleteKey.mutateAsync(deleteTarget.id)
      toast({ title: 'Deleted' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
    setDeleteTarget(null)
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pwForm.new1 !== pwForm.new2) {
      toast({ title: 'Passwords do not match', variant: 'destructive' })
      return
    }
    try {
      await changePassword(pwForm.current, pwForm.new1)
      toast({ title: 'Password changed' })
      setPwForm({ current: '', new1: '', new2: '' })
    } catch (err: any) {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">Credentials, integrations and security</p>
      </div>

      {/* Cloudflare Configs */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Cloud className="w-4 h-4 text-orange-400" />
            </div>
            <h3 className="text-lg font-semibold">Cloudflare Configs</h3>
          </div>
          <button onClick={() => setShowCfForm(!showCfForm)} className={showCfForm ? 'btn-ghost text-xs' : 'btn-primary text-xs flex items-center gap-1.5'}>
            {showCfForm ? 'Cancel' : <><Plus className="w-3 h-3" /> Add Config</>}
          </button>
        </div>
        {showCfForm && (
          <form onSubmit={handleCreateCf} className="glass rounded-lg p-4 mb-3 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
                <input value={cfForm.name} onChange={e => setCfForm({...cfForm, name: e.target.value})} className="input-glass" required />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Base Domain</label>
                <input value={cfForm.base_domain} onChange={e => setCfForm({...cfForm, base_domain: e.target.value})} className="input-glass font-mono" placeholder="example.com" required />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Zone ID</label>
                <input value={cfForm.zone_id} onChange={e => setCfForm({...cfForm, zone_id: e.target.value})} className="input-glass font-mono" required />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">API Token</label>
                <input type="password" value={cfForm.api_token} onChange={e => setCfForm({...cfForm, api_token: e.target.value})} className="input-glass" required />
              </div>
            </div>
            <button type="submit" disabled={createCf.isPending} className="btn-primary text-xs">
              Save
            </button>
          </form>
        )}
        <div className="glass rounded-lg overflow-hidden divide-y divide-border/50">
          {cfConfigs?.map(c => (
            <div key={c.id} className="flex items-center justify-between px-4 py-3 hover:bg-accent/30 transition-colors">
              <div>
                <p className="text-sm font-medium">{c.name}</p>
                <p className="text-xs text-muted-foreground font-mono">{c.base_domain} &middot; {c.zone_id.slice(0, 12)}...</p>
              </div>
              <button onClick={() => setDeleteTarget({ type: 'cf', id: c.id })} className="text-xs px-2.5 py-1 rounded-md border border-red-600/40 text-red-400 hover:bg-red-500/10 transition-all inline-flex items-center gap-1">
                <Trash2 className="w-3 h-3" />
                Delete
              </button>
            </div>
          ))}
          {(!cfConfigs || cfConfigs.length === 0) && (
            <div className="px-4 py-8 text-center">
              <Cloud className="w-6 h-6 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No Cloudflare configs</p>
            </div>
          )}
        </div>
      </section>

      {/* SSH Keys */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
              <KeyRound className="w-4 h-4 text-violet-400" />
            </div>
            <h3 className="text-lg font-semibold">SSH Keys</h3>
          </div>
          <button onClick={() => setShowKeyForm(!showKeyForm)} className={showKeyForm ? 'btn-ghost text-xs' : 'btn-primary text-xs flex items-center gap-1.5'}>
            {showKeyForm ? 'Cancel' : <><Plus className="w-3 h-3" /> Register Key</>}
          </button>
        </div>
        {showKeyForm && (
          <form onSubmit={handleCreateKey} className="glass rounded-lg p-4 mb-3 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
                <input value={keyForm.name} onChange={e => setKeyForm({...keyForm, name: e.target.value})} className="input-glass" required />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-muted-foreground">Key Path (in container)</label>
                <input value={keyForm.private_key_path} onChange={e => setKeyForm({...keyForm, private_key_path: e.target.value})} className="input-glass font-mono" placeholder="/app/ssh_keys/id_ed25519" required />
              </div>
            </div>
            <button type="submit" disabled={createKey.isPending} className="btn-primary text-xs">
              Register
            </button>
          </form>
        )}
        <div className="glass rounded-lg overflow-hidden divide-y divide-border/50">
          {sshKeys?.map(k => (
            <div key={k.id} className="flex items-center justify-between px-4 py-3 hover:bg-accent/30 transition-colors">
              <div>
                <p className="text-sm font-medium">{k.name}</p>
                <p className="text-xs text-muted-foreground font-mono">{k.private_key_path}{k.fingerprint ? ` (${k.fingerprint.slice(0, 24)}...)` : ''}</p>
              </div>
              <button onClick={() => setDeleteTarget({ type: 'ssh', id: k.id })} className="text-xs px-2.5 py-1 rounded-md border border-red-600/40 text-red-400 hover:bg-red-500/10 transition-all inline-flex items-center gap-1">
                <Trash2 className="w-3 h-3" />
                Delete
              </button>
            </div>
          ))}
          {(!sshKeys || sshKeys.length === 0) && (
            <div className="px-4 py-8 text-center">
              <KeyRound className="w-6 h-6 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No SSH keys registered</p>
            </div>
          )}
        </div>
      </section>

      {/* Change Password */}
      <section>
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Lock className="w-4 h-4 text-primary" />
          </div>
          <h3 className="text-lg font-semibold">Change Password</h3>
        </div>
        <form onSubmit={handleChangePassword} className="glass rounded-lg p-5 space-y-3 max-w-sm">
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">Current Password</label>
            <input type="password" value={pwForm.current} onChange={e => setPwForm({...pwForm, current: e.target.value})} className="input-glass" required />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">New Password</label>
            <input type="password" value={pwForm.new1} onChange={e => setPwForm({...pwForm, new1: e.target.value})} className="input-glass" required />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">Confirm New Password</label>
            <input type="password" value={pwForm.new2} onChange={e => setPwForm({...pwForm, new2: e.target.value})} className="input-glass" required />
          </div>
          <button type="submit" className="btn-primary text-xs">
            Change Password
          </button>
        </form>
      </section>

      <ConfirmDialog open={!!deleteTarget} title="Confirm Delete" description="Are you sure? This action cannot be undone." confirmText="Delete" destructive onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />
    </div>
  )
}
