import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface VPNUser {
  id: string
  username: string
  uuid: string
  hysteria2_password: string
  sub_token: string | null
  traffic_limit_bytes: number | null
  traffic_used_bytes: number
  expires_at: string | null
  enabled: boolean
  created_at: string
  traffic_by_server?: Array<{ server_id: string; bytes_up: number; bytes_down: number }>
}

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get('/users')
      return data as VPNUser[]
    },
    refetchInterval: 30000,
  })
}

export function useUser(id: string) {
  return useQuery({
    queryKey: ['users', id],
    queryFn: async () => {
      const { data } = await api.get(`/users/${id}`)
      return data as VPNUser
    },
    enabled: !!id,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { username: string; traffic_limit_bytes?: number | null; expires_at?: string | null }) => {
      const { data } = await api.post('/users', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; username?: string; traffic_limit_bytes?: number | null; expires_at?: string | null; enabled?: boolean }) => {
      const { data } = await api.patch(`/users/${id}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/users/${id}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}
