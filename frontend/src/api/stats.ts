import { useQuery } from '@tanstack/react-query'
import api from './client'

export interface Stats {
  total_servers: number
  online_servers: number
  total_users: number
  active_users: number
  total_traffic_bytes: number
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data } = await api.get('/stats/summary')
      return data as Stats
    },
    refetchInterval: 30000,
  })
}
