import type { Node, Edge } from '@xyflow/react'

export interface ValidationMessage {
  type: 'error' | 'warning' | 'info'
  code: string
  message: string
}

export interface ValidationResult {
  is_valid: boolean
  errors: ValidationMessage[]
  warnings: ValidationMessage[]
  info: ValidationMessage[]
}

const TLS_PROTOCOLS = new Set(['vless', 'trojan', 'hysteria2'])

export function validateGraph(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: ValidationMessage[] = []
  const warnings: ValidationMessage[] = []
  const info: ValidationMessage[] = []

  const nodeMap = new Map(nodes.map(n => [n.id, n]))
  const outgoing = new Map<string, Edge[]>()
  const incoming = new Map<string, Edge[]>()

  for (const e of edges) {
    if (!outgoing.has(e.source)) outgoing.set(e.source, [])
    outgoing.get(e.source)!.push(e)
    if (!incoming.has(e.target)) incoming.set(e.target, [])
    incoming.get(e.target)!.push(e)
  }

  // Find client node
  const clientNodes = nodes.filter(n => n.type === 'clientNode')
  if (clientNodes.length === 0) {
    errors.push({ type: 'error', code: 'NO_CLIENT', message: 'Client node is missing' })
    return { is_valid: false, errors, warnings, info }
  }

  const clientId = clientNodes[0].id
  const clientOut = outgoing.get(clientId) || []

  if (clientOut.length === 0) {
    errors.push({ type: 'error', code: 'CLIENT_NO_OUTPUT', message: 'Client node has no outgoing connection' })
  } else if (clientOut.length > 1) {
    errors.push({ type: 'error', code: 'CLIENT_MULTI_OUTPUT', message: 'Client node must have exactly one outgoing connection' })
  }

  // Cycle detection
  const visited = new Set<string>()
  const recStack = new Set<string>()

  function hasCycle(nodeId: string): boolean {
    visited.add(nodeId)
    recStack.add(nodeId)
    for (const edge of outgoing.get(nodeId) || []) {
      if (!visited.has(edge.target)) {
        if (hasCycle(edge.target)) return true
      } else if (recStack.has(edge.target)) {
        return true
      }
    }
    recStack.delete(nodeId)
    return false
  }

  if (hasCycle(clientId)) {
    errors.push({ type: 'error', code: 'CYCLE', message: 'Cycle detected in graph' })
  }

  // Reachability BFS
  const reachable = new Set<string>()
  const queue = [clientId]
  while (queue.length > 0) {
    const nid = queue.shift()!
    if (reachable.has(nid)) continue
    reachable.add(nid)
    for (const edge of outgoing.get(nid) || []) {
      queue.push(edge.target)
    }
  }

  // Orphan detection
  for (const n of nodes) {
    if (!reachable.has(n.id) && n.type !== 'clientNode') {
      const label = (n.data as Record<string, unknown>)?.label as string || n.id
      errors.push({ type: 'error', code: 'ORPHAN', message: `Node '${label}' is not connected to Client` })
    }
  }

  const terminalTypes = new Set(['serverNode', 'directNode'])

  function checkPaths(nodeId: string, depth: number, path: string[]): void {
    const node = nodeMap.get(nodeId)
    if (!node) return
    const ntype = node.type || ''
    const data = node.data as Record<string, unknown>
    const outs = outgoing.get(nodeId) || []

    if (terminalTypes.has(ntype) && outs.length === 0) {
      if (depth > 3) {
        warnings.push({
          type: 'warning', code: 'DEEP_CHAIN',
          message: `Chain depth >3 hops — latency will be high (${path.join(' → ')})`,
        })
      }
      return
    }

    if (ntype === 'directNode') return
    if (ntype === 'serverNode' && outs.length === 0) return

    if (outs.length === 0 && !terminalTypes.has(ntype)) {
      const label = data?.label as string || nodeId
      errors.push({ type: 'error', code: 'NO_TERMINAL', message: `Path leads nowhere at node '${label}'` })
      return
    }

    if (ntype === 'strategyNode' && outs.length < 2) {
      const label = data?.label as string || nodeId
      errors.push({ type: 'error', code: 'STRATEGY_LOW_OUTPUTS', message: `Strategy node '${label}' needs at least 2 outputs` })
    }

    for (const edge of outs) {
      const targetNode = nodeMap.get(edge.target)
      if (!targetNode) continue
      const targetData = targetNode.data as Record<string, unknown>
      const targetLabel = targetData?.label as string || edge.target
      const newPath = [...path, targetLabel]

      // TLS-over-TLS
      if (ntype === 'serverNode' && targetNode.type === 'serverNode') {
        const srcProto = ((data?.protocol as string) || '').toLowerCase()
        const dstProto = ((targetData?.protocol as string) || '').toLowerCase()
        if (TLS_PROTOCOLS.has(srcProto) && TLS_PROTOCOLS.has(dstProto)) {
          warnings.push({
            type: 'warning', code: 'TLS_OVER_TLS',
            message: `TLS-over-TLS: ${data?.label} → ${targetLabel} — may cause failures. Use SSH/Shadowsocks for the jump hop.`,
          })
        }
      }

      // SS as first hop
      if (nodeId === clientId && targetNode.type === 'serverNode') {
        const proto = ((targetData?.protocol as string) || '').toLowerCase()
        if (proto === 'shadowsocks') {
          warnings.push({
            type: 'warning', code: 'SS_FIRST_HOP',
            message: 'Shadowsocks as first hop — detectable by DPI. Consider SSH instead.',
          })
        }
      }

      const hopDepth = depth + (targetNode.type === 'serverNode' ? 1 : 0)
      checkPaths(edge.target, hopDepth, newPath)
    }
  }

  if (clientOut.length > 0) {
    checkPaths(clientId, 0, ['Client'])
  }

  // Offline server warnings
  for (const n of nodes) {
    if (n.type === 'serverNode') {
      const data = n.data as Record<string, unknown>
      const status = data?.status as string
      if (status === 'offline' || status === 'error') {
        warnings.push({
          type: 'warning', code: 'SERVER_OFFLINE',
          message: `Server '${data?.label}' is currently ${status}`,
        })
      }
    }
  }

  // Chain summary
  if (errors.length === 0) {
    buildChainInfo(clientId, outgoing, nodeMap, info)
  }

  return { is_valid: errors.length === 0, errors, warnings, info }
}

const HOP_LATENCY: Record<string, number> = {
  ssh: 30, shadowsocks: 20, vless: 25, hysteria2: 15,
}

function buildChainInfo(
  clientId: string,
  outgoing: Map<string, Edge[]>,
  nodeMap: Map<string, Node>,
  info: ValidationMessage[],
): void {
  function walk(nid: string): [string[], number] {
    const node = nodeMap.get(nid)
    if (!node) return [[], 0]
    const data = node.data as Record<string, unknown>
    const label = (data?.label as string) || nid
    const outs = outgoing.get(nid) || []

    if (node.type === 'directNode' || (node.type === 'serverNode' && outs.length === 0)) {
      const proto = ((data?.protocol as string) || '').toLowerCase()
      const lat = node.type === 'serverNode' ? (HOP_LATENCY[proto] ?? 25) : 0
      return [[label], lat]
    }

    if (outs.length > 0) {
      const [rest, restLat] = walk(outs[0].target)
      const proto = ((data?.protocol as string) || '').toLowerCase()
      const lat = node.type === 'serverNode' ? (HOP_LATENCY[proto] ?? 0) : 0
      return [[label, ...rest], lat + restLat]
    }

    return [[label], 0]
  }

  const [chain, totalLat] = walk(clientId)
  let serverCount = 0
  for (const label of chain) {
    for (const [, n] of nodeMap) {
      const d = n.data as Record<string, unknown>
      if ((d?.label as string) === label && n.type === 'serverNode') {
        serverCount++
        break
      }
    }
  }

  info.push({
    type: 'info', code: 'CHAIN_SUMMARY',
    message: `Chain: ${chain.join(' → ')} (${serverCount} hop${serverCount !== 1 ? 's' : ''})`,
  })
  if (totalLat > 0) {
    info.push({ type: 'info', code: 'ESTIMATED_RTT', message: `Estimated RTT: ~${totalLat}ms` })
  }
}
