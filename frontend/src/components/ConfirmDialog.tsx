import { AlertTriangle } from 'lucide-react'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  onConfirm: () => void
  onCancel: () => void
  confirmText?: string
  destructive?: boolean
  loading?: boolean
}

export default function ConfirmDialog({
  open, title, description, onConfirm, onCancel, confirmText = 'Confirm', destructive = false, loading = false
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="modal-overlay">
      <div className="modal-backdrop" onClick={loading ? undefined : onCancel} />
      <div className="modal-content max-w-md p-6">
        <div className="flex items-start gap-3">
          {destructive && (
            <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center flex-none mt-0.5">
              <AlertTriangle className="w-4.5 h-4.5 text-red-400" />
            </div>
          )}
          <div>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onCancel} className="btn-ghost" disabled={loading}>
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-sm rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 ${
              destructive
                ? 'bg-red-600 hover:bg-red-500 text-white hover:shadow-[0_0_16px_-4px_rgba(239,68,68,0.35)]'
                : 'btn-primary'
            }`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                {confirmText}...
              </span>
            ) : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
