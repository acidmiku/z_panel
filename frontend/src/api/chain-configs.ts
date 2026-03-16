import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface ChainConfig {
  id: string
  user_id: string
  name: string
  description: string | null
  graph_data: GraphData
  generated_config: Record<string, unknown> | null
  is_valid: boolean
  validation_errors: ValidationMessage[] | null
  created_at: string
  updated_at: string
}

export interface ChainConfigListItem {
  id: string
  name: string
  description: string | null
  is_valid: boolean
  created_at: string
  updated_at: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
}

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

export function useChainConfigs() {
  return useQuery({
    queryKey: ['chain-configs'],
    queryFn: async () => {
      const { data } = await api.get('/chain-configs')
      return data as ChainConfigListItem[]
    },
  })
}

export function useChainConfig(id: string | null) {
  return useQuery({
    queryKey: ['chain-configs', id],
    queryFn: async () => {
      const { data } = await api.get(`/chain-configs/${id}`)
      return data as ChainConfig
    },
    enabled: !!id,
  })
}

export function useCreateChainConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string; graph_data: GraphData }) => {
      const { data } = await api.post('/chain-configs', body)
      return data as ChainConfig
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chain-configs'] }),
  })
}

export function useUpdateChainConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & Record<string, unknown>) => {
      const { data } = await api.patch(`/chain-configs/${id}`, body)
      return data as ChainConfig
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['chain-configs'] })
      qc.invalidateQueries({ queryKey: ['chain-configs', vars.id] })
    },
  })
}

export function useDeleteChainConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/chain-configs/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chain-configs'] }),
  })
}

export function useValidateGraph() {
  return useMutation({
    mutationFn: async (graphData: GraphData) => {
      const { data } = await api.post('/chain-configs/validate', graphData)
      return data as ValidationResult
    },
  })
}

export function useExportChainConfig() {
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/chain-configs/${id}/export`)
      return data as Record<string, unknown>
    },
  })
}

export interface ImportFromProfileResult {
  graph_data: GraphData
  user_name: string
  server_count: number
  has_jumphost: boolean
  has_routing: boolean
}

export function useImportFromProfile() {
  return useMutation({
    mutationFn: async (userId: string) => {
      const { data } = await api.post(`/chain-configs/import-from-profile/${userId}`)
      return data as ImportFromProfileResult
    },
  })
}
