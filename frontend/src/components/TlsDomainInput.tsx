import { useState, useRef, useEffect } from 'react'
import { useSuggestTlsDomain } from '@/api/utils'
import { Sparkles } from 'lucide-react'

interface Props {
  value: string
  onChange: (v: string) => void
  ip: string | null
  className?: string
}

export default function TlsDomainInput({ value, onChange, ip, className = '' }: Props) {
  const { data, isLoading } = useSuggestTlsDomain(ip)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const suggestions = data?.suggestions || []
  const isProviderDetected = suggestions.length > 0 && suggestions[0] !== 'www.google.com'

  return (
    <div ref={ref} className="relative">
      <label className="block text-xs font-medium mb-1 text-muted-foreground">TLS Fronting Domain</label>
      <div className="relative">
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          className={`input-glass font-mono pr-8 ${className}`}
          placeholder="www.google.com"
        />
        {suggestions.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className={`absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded transition-colors ${
              isProviderDetected
                ? 'text-amber-400/70 hover:text-amber-400'
                : 'text-muted-foreground/50 hover:text-muted-foreground'
            }`}
            title={isProviderDetected ? 'Provider-matched suggestions' : 'Domain suggestions'}
          >
            <Sparkles className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {open && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-border/60 bg-popover shadow-xl overflow-hidden">
          <div className="px-3 py-1.5 border-b border-border/30">
            <span className={`text-[10px] font-medium uppercase tracking-wider ${isProviderDetected ? 'text-amber-400/70' : 'text-muted-foreground/60'}`}>
              {isProviderDetected ? 'Matched to hosting provider' : 'Common fronting domains'}
            </span>
          </div>
          {suggestions.map(d => (
            <button
              key={d}
              type="button"
              onClick={() => { onChange(d); setOpen(false) }}
              className={`w-full text-left px-3 py-1.5 text-sm font-mono hover:bg-accent/50 transition-colors ${value === d ? 'text-primary bg-primary/5' : 'text-foreground'}`}
            >
              {d}
            </button>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground mt-0.5 opacity-60">
        DPI sees this domain in TLS handshake
        {isProviderDetected && <span className="text-amber-400/60 ml-1">— provider detected</span>}
      </p>
    </div>
  )
}
