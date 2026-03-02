import { useState, useEffect, useRef } from 'react'
import type { Node, Edge } from '@xyflow/react'
import { validateGraph, type ValidationResult } from '../utils/graphValidator'

const EMPTY: ValidationResult = { is_valid: true, errors: [], warnings: [], info: [] }
const DEBOUNCE_MS = 800

export function useGraphValidation(nodes: Node[], edges: Edge[]): ValidationResult {
  const [result, setResult] = useState<ValidationResult>(EMPTY)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Skip validation when graph only has the default client node with no edges
  const isMinimal = nodes.length <= 1 && edges.length === 0

  useEffect(() => {
    if (isMinimal) {
      setResult(EMPTY)
      return
    }

    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      setResult(validateGraph(nodes, edges))
    }, DEBOUNCE_MS)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [nodes, edges, isMinimal])

  return result
}
