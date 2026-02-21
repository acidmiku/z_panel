import { useState, useEffect, useCallback } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

interface Toast {
  id: number
  title: string
  description?: string
  variant?: 'default' | 'destructive'
}

let globalToast: (t: Omit<Toast, 'id'>) => void = () => {}

export function useToast() {
  return { toast: globalToast }
}

export function toast(t: Omit<Toast, 'id'>) {
  globalToast(t)
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now()
    setToasts(prev => [...prev, { ...t, id }])
    setTimeout(() => {
      setToasts(prev => prev.filter(x => x.id !== id))
    }, 4000)
  }, [])

  useEffect(() => {
    globalToast = addToast
  }, [addToast])

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`glass rounded-lg px-4 py-3 shadow-lg animate-enter flex items-start gap-3 ${
            t.variant === 'destructive'
              ? 'bg-red-950/80 border-red-700/40 text-red-100'
              : ''
          }`}
          style={t.variant !== 'destructive' ? {
            boxShadow: '0 0 16px -4px hsla(var(--glow-cyan), 0.1), 0 8px 24px hsla(228, 16%, 2%, 0.4)'
          } : undefined}
        >
          {t.variant === 'destructive' ? (
            <XCircle className="w-4 h-4 text-red-400 flex-none mt-0.5" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-primary flex-none mt-0.5" />
          )}
          <div>
            <p className="font-semibold text-sm">{t.title}</p>
            {t.description && <p className="text-xs mt-0.5 text-muted-foreground">{t.description}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}
