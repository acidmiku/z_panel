import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface Jumphost {
  id: string
  name: string
  ip: string
  ssh_port: number
  ssh_user: string
  ssh_key_id: string
  shadowsocks_port: number | null
  shadowsocks_method: string
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
  mtproxy_relay_server_id: string | null
  created_at: string
}

export interface TrafficRate {
  timestamp: string
  rx_rate: number
  tx_rate: number
}

export function useJumphosts() {
  return useQuery({
    queryKey: ['jumphosts'],
    queryFn: async () => {
      const { data } = await api.get('/jumphosts')
      return data as Jumphost[]
    },
    refetchInterval: (query) => {
      const jumphosts = query.state.data as Jumphost[] | undefined
      const anyProvisioning = jumphosts?.some(j => j.status === 'provisioning')
      return anyProvisioning ? 3000 : 30000
    },
  })
}

export function useJumphost(id: string) {
  return useQuery({
    queryKey: ['jumphosts', id],
    queryFn: async () => {
      const { data } = await api.get(`/jumphosts/${id}`)
      return data as Jumphost
    },
    enabled: !!id,
  })
}

export function useCreateJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const { data } = await api.post('/jumphosts', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useUpdateJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & Record<string, unknown>) => {
      const { data } = await api.patch(`/jumphosts/${id}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useDeleteJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, force = false }: { id: string; force?: boolean }) => {
      const { data } = await api.delete(`/jumphosts/${id}`, { params: force ? { force: true } : undefined })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useSyncJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/jumphosts/${id}/sync`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useReinstallJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/jumphosts/${id}/reinstall`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useInstallMtproxyJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, port, tls_domain }: { id: string; port: number; tls_domain: string }) => {
      const { data } = await api.post(`/jumphosts/${id}/install-mtproxy`, { port, tls_domain })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useUninstallMtproxyJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/jumphosts/${id}/uninstall-mtproxy`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useSetupRelayJumphost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, server_id, port, tls_domain }: { id: string; server_id: string; port: number; tls_domain: string }) => {
      const { data } = await api.post(`/jumphosts/${id}/setup-relay`, { server_id, port, tls_domain })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jumphosts'] }),
  })
}

export function useJumphostLogs(id: string | null) {
  return useQuery({
    queryKey: ['jumphosts', id, 'logs'],
    queryFn: async () => {
      const { data } = await api.get(`/jumphosts/${id}/logs`)
      return data as { logs: string }
    },
    enabled: !!id,
    refetchInterval: false,
  })
}

export function useJumphostTrafficHistory(id: string | null) {
  return useQuery({
    queryKey: ['jumphosts', id, 'traffic-history'],
    queryFn: async () => {
      const { data } = await api.get(`/jumphosts/${id}/traffic-history`)
      return data as { jumphost_id: string; rates: TrafficRate[] }
    },
    enabled: !!id,
    refetchInterval: 60000,
  })
}
