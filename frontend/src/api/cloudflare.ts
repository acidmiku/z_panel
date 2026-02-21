import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface CloudflareConfig {
  id: string
  name: string
  zone_id: string
  base_domain: string
  created_at: string
}

export function useCloudflareConfigs() {
  return useQuery({
    queryKey: ['cloudflare-configs'],
    queryFn: async () => {
      const { data } = await api.get('/cloudflare-configs')
      return data as CloudflareConfig[]
    },
  })
}

export function useCreateCloudflareConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; api_token: string; zone_id: string; base_domain: string }) => {
      const { data } = await api.post('/cloudflare-configs', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cloudflare-configs'] }),
  })
}

export function useDeleteCloudflareConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/cloudflare-configs/${id}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cloudflare-configs'] }),
  })
}
