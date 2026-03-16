import type { Node, Edge } from '@xyflow/react'

export interface GraphData {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }>
  edges: Array<{ id: string; source: string; target: string; sourceHandle?: string; targetHandle?: string }>
}

export function serializeGraph(nodes: Node[], edges: Edge[]): GraphData {
  return {
    nodes: nodes.map(n => ({
      id: n.id,
      type: n.type || 'default',
      position: n.position,
      data: n.data as Record<string, unknown>,
    })),
    edges: edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle || undefined,
      targetHandle: e.targetHandle || undefined,
    })),
  }
}

export function deserializeGraph(data: GraphData): { nodes: Node[]; edges: Edge[] } {
  return {
    nodes: data.nodes.map(n => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: n.data,
      deletable: n.type !== 'clientNode',
    })),
    edges: data.edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      type: 'detour',
      animated: true,
    })),
  }
}
