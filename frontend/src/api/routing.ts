import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface RoutingRule {
  id: string
  user_id: string | null
  domain_pattern: string
  match_type: 'domain' | 'domain-suffix' | 'domain-keyword' | 'domain-regex'
  action: 'proxy' | 'direct'
  order: number
  created_at: string
}

export interface GeoRuleEntry {
  id: string
  action: 'DIRECT' | 'Proxy' | 'REJECT'
}

export interface UserRoutingConfig {
  id: string
  user_id: string
  geo_rules: GeoRuleEntry[] | null
  jumphost_id: string | null
  jumphost_protocol: 'ss' | 'ssh'
  created_at: string
  updated_at: string
}

export interface GeoOption {
  id: string
  label: string
  default_action: 'DIRECT' | 'Proxy' | 'REJECT'
}

export function useRoutingRules(userId: string) {
  return useQuery({
    queryKey: ['routing', 'rules', userId],
    queryFn: async () => {
      const { data } = await api.get(`/routing/rules/${userId}`)
      return data as RoutingRule[]
    },
    enabled: !!userId,
  })
}

export function useCreateRoutingRule(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { domain_pattern: string; match_type: string; action: string; order?: number }) => {
      const { data } = await api.post(`/routing/rules/${userId}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routing', 'rules', userId] }),
  })
}

export function useUpdateRoutingRule(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; domain_pattern?: string; match_type?: string; action?: string; order?: number }) => {
      const { data } = await api.put(`/routing/rules/${id}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routing', 'rules', userId] }),
  })
}

export function useDeleteRoutingRule(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/routing/rules/${id}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routing', 'rules', userId] }),
  })
}

export function useRoutingConfig(userId: string) {
  return useQuery({
    queryKey: ['routing', 'config', userId],
    queryFn: async () => {
      const { data } = await api.get(`/routing/config/${userId}`)
      return data as UserRoutingConfig
    },
    enabled: !!userId,
    retry: false,
  })
}

export function useUpsertRoutingConfig(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { geo_rules?: GeoRuleEntry[] | null; jumphost_id?: string | null; jumphost_protocol?: string }) => {
      const { data } = await api.put(`/routing/config/${userId}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routing', 'config', userId] }),
  })
}

export function useGeoOptions() {
  return useQuery({
    queryKey: ['routing', 'geo-options'],
    queryFn: async () => {
      const { data } = await api.get('/routing/geo-options')
      return data as GeoOption[]
    },
    staleTime: Infinity,
  })
}
