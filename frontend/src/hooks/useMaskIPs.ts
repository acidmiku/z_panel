import { useState, useCallback } from 'react'

const MASK_KEY = 'z-panel-mask-ips'

export function useMaskIPs() {
  const [masked, setMasked] = useState(() => {
    return localStorage.getItem(MASK_KEY) === 'true'
  })

  const toggle = useCallback(() => {
    setMasked(prev => {
      const next = !prev
      localStorage.setItem(MASK_KEY, String(next))
      return next
    })
  }, [])

  const mask = useCallback((value: string | null | undefined): string => {
    if (!value) return ''
    if (!masked) return value

    // Mask IP addresses: 1.2.3.4 → •••.•••.•••.•••
    const ipMasked = value.replace(
      /\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b/g,
      '•••.•••.•••.•••'
    )

    // If the whole value is an IP, return as-is from above
    if (ipMasked !== value) return ipMasked

    // Mask FQDNs: sub.domain.com → ••••••••.domain.com (keep TLD+1)
    const parts = value.split('.')
    if (parts.length >= 2) {
      const keep = parts.slice(-2).join('.')
      return '••••••••.' + keep
    }

    return value
  }, [masked])

  return { masked, toggle, mask }
}
