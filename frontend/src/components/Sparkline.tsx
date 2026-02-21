interface SparklineProps {
  data: number[]
  label?: string
  width?: number
  height?: number
  className?: string
  formatValue?: (v: number) => string
}

function defaultFormat(v: number): string {
  if (v < 1024) return `${v} B/s`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB/s`
  if (v < 1024 * 1024 * 1024) return `${(v / (1024 * 1024)).toFixed(1)} MB/s`
  return `${(v / (1024 * 1024 * 1024)).toFixed(2)} GB/s`
}

export default function Sparkline({ data, label, width = 120, height = 32, className = '', formatValue = defaultFormat }: SparklineProps) {
  if (data.length < 2) {
    return (
      <div className={`flex items-center justify-center text-xs text-muted-foreground opacity-50 ${className}`} style={{ height }}>
        Waiting for data...
      </div>
    )
  }

  const max = Math.max(...data, 1)
  const current = data[data.length - 1]
  const svgH = height
  const padding = 2

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2)
    const y = svgH - padding - (v / max) * (svgH - padding * 2)
    return `${x},${y}`
  })

  const polyline = points.join(' ')

  const firstX = padding
  const lastX = padding + ((data.length - 1) / (data.length - 1)) * (width - padding * 2)
  const areaPath = `M ${points[0]} ${points.slice(1).map(p => `L ${p}`).join(' ')} L ${lastX},${svgH} L ${firstX},${svgH} Z`

  // Unique gradient ID to avoid conflicts when multiple sparklines are on page
  const gradId = `sparkFill-${label?.replace(/\s/g, '') || 'default'}`

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-1">
        {label && <span className="text-xs text-muted-foreground">{label}</span>}
        <span className="text-xs font-mono font-medium text-primary">{formatValue(current)}</span>
      </div>
      <svg width="100%" height={svgH} viewBox={`0 0 ${width} ${svgH}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.25" />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${gradId})`} />
        <polyline
          points={polyline}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}
