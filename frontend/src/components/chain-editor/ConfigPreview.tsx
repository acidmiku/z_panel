import { useState } from 'react'
import { X, Copy, Download, Check } from 'lucide-react'

interface Props {
  config: Record<string, unknown> | null
  onClose: () => void
}

export default function ConfigPreview({ config, onClose }: Props) {
  const [copied, setCopied] = useState(false)

  if (!config) return null

  const jsonStr = JSON.stringify(config, null, 2)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonStr)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([jsonStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sing-box-config.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-backdrop" />
      <div
        className="modal-content max-w-3xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/40">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Generated Config</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5">sing-box client configuration</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="btn-ghost flex items-center gap-1.5 !px-3 !py-1.5 text-xs"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              onClick={handleDownload}
              className="btn-primary flex items-center gap-1.5 !px-3 !py-1.5 text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-accent/50 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* JSON Content */}
        <div className="p-6 max-h-[60vh] overflow-auto">
          <pre className="text-[11px] leading-relaxed font-mono text-foreground/90 whitespace-pre-wrap break-words">
            {jsonStr}
          </pre>
        </div>
      </div>
    </div>
  )
}
