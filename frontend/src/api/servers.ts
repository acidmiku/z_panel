import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface Server {
  id: string
  name: string
  ip: string
  ssh_port: number
  ssh_user: string
  ssh_key_id: string
  cf_config_id: string
  subdomain: string | null
  fqdn: string | null
  subdomain_prefix: string | null
  hysteria2_port: number
  reality_port: number
  reality_public_key: string | null
  reality_short_id: string | null
  reality_dest: string
  reality_server_name: string
  hardened: boolean
  status: 'provisioning' | 'online' | 'offline' | 'error'
  status_message: string | null
  last_health_check: string | null
  sing_box_version: string | null
  system_stats: {
    uptime_seconds?: number
    load_avg?: [number, number, number]
    memory_total?: number
    memory_used?: number
    disk_total?: number
    disk_used?: number
  } | null
  mtproxy_enabled: boolean
  mtproxy_port: number | null
  mtproxy_tls_domain: string | null
  mtproxy_link: string | null
  created_at: string
}

export interface TrafficRate {
  timestamp: string
  rx_rate: number
  tx_rate: number
}

export function useServers() {
  return useQuery({
    queryKey: ['servers'],
    queryFn: async () => {
      const { data } = await api.get('/servers')
      return data as Server[]
    },
    refetchInterval: (query) => {
      const servers = query.state.data as Server[] | undefined
      const anyProvisioning = servers?.some(s => s.status === 'provisioning')
      return anyProvisioning ? 3000 : 30000
    },
  })
}

export function useServer(id: string) {
  return useQuery({
    queryKey: ['servers', id],
    queryFn: async () => {
      const { data } = await api.get(`/servers/${id}`)
      return data as Server
    },
    enabled: !!id,
  })
}

export function useCreateServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const { data } = await api.post('/servers', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useBatchCreateServers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const { data } = await api.post('/servers/batch', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useUpdateServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & Record<string, unknown>) => {
      const { data } = await api.patch(`/servers/${id}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useDeleteServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, force = false }: { id: string; force?: boolean }) => {
      const { data } = await api.delete(`/servers/${id}`, { params: force ? { force: true } : undefined })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useSyncServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/servers/${id}/sync`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useReinstallServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/servers/${id}/reinstall`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useServerLogs(id: string | null) {
  return useQuery({
    queryKey: ['servers', id, 'logs'],
    queryFn: async () => {
      const { data } = await api.get(`/servers/${id}/logs`)
      return data as { logs: string }
    },
    enabled: !!id,
    refetchInterval: false,
  })
}

export function useInstallMtproxyServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, port, tls_domain }: { id: string; port: number; tls_domain: string }) => {
      const { data } = await api.post(`/servers/${id}/install-mtproxy`, { port, tls_domain })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useUninstallMtproxyServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/servers/${id}/uninstall-mtproxy`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servers'] }),
  })
}

export function useServerTrafficHistory(id: string | null) {
  return useQuery({
    queryKey: ['servers', id, 'traffic-history'],
    queryFn: async () => {
      const { data } = await api.get(`/servers/${id}/traffic-history`)
      return data as { server_id: string; rates: TrafficRate[] }
    },
    enabled: !!id,
    refetchInterval: 60000,
  })
}
