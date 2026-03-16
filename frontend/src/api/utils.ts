import { useQuery } from '@tanstack/react-query'
import api from './client'

export function useSuggestTlsDomain(ip: string | null) {
  return useQuery({
    queryKey: ['suggest-tls-domain', ip],
    queryFn: async () => {
      const { data } = await api.get('/utils/suggest-tls-domain', { params: { ip } })
      return data as { ip: string; suggestions: string[] }
    },
    enabled: !!ip && ip.length >= 7,
    staleTime: 5 * 60 * 1000,
  })
}
