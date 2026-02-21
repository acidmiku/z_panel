import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export interface SSHKey {
  id: string
  name: string
  private_key_path: string
  fingerprint: string | null
  created_at: string
}

export function useSSHKeys() {
  return useQuery({
    queryKey: ['ssh-keys'],
    queryFn: async () => {
      const { data } = await api.get('/ssh-keys')
      return data as SSHKey[]
    },
  })
}

export function useCreateSSHKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; private_key_path: string }) => {
      const { data } = await api.post('/ssh-keys', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ssh-keys'] }),
  })
}

export function useDeleteSSHKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/ssh-keys/${id}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ssh-keys'] }),
  })
}
