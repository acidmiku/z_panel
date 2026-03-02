import { AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react'
import type { ValidationResult } from './utils/graphValidator'

interface Props {
  validation: ValidationResult | null
}

export default function ValidationPanel({ validation }: Props) {
  if (!validation) return null

  const { errors, warnings, info, is_valid } = validation
  const hasMessages = errors.length > 0 || warnings.length > 0 || info.length > 0

  return (
    <div className="border-t border-border/40 glass-subtle">
      <div className="px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
            Validation
          </span>
          {is_valid && errors.length === 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] text-green-400">
              <CheckCircle2 className="w-3 h-3" />
              Valid
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          {errors.length > 0 && (
            <span className="text-red-400">{errors.length} error{errors.length !== 1 ? 's' : ''}</span>
          )}
          {warnings.length > 0 && (
            <span className="text-yellow-400">{warnings.length} warning{warnings.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>

      {hasMessages && (
        <div className="px-4 pb-2 max-h-32 overflow-y-auto space-y-1">
          {errors.map((msg, i) => (
            <div key={`e-${i}`} className="flex items-start gap-2 text-[11px]">
              <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" />
              <span className="text-red-300">{msg.message}</span>
            </div>
          ))}
          {warnings.map((msg, i) => (
            <div key={`w-${i}`} className="flex items-start gap-2 text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5 text-yellow-400 mt-0.5 flex-shrink-0" />
              <span className="text-yellow-300">{msg.message}</span>
            </div>
          ))}
          {info.map((msg, i) => (
            <div key={`i-${i}`} className="flex items-start gap-2 text-[11px]">
              <Info className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" />
              <span className="text-blue-300">{msg.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
