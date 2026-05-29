import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import type { PollerDisplay, PollerHealth } from './types'
import { derivePollerDisplay } from './utils'

export function usePollers() {
  return useQuery<PollerHealth[], Error, PollerDisplay[]>({
    queryKey: ['pollers'],
    queryFn: () => apiFetch<PollerHealth[]>('/admin/pollers'),
    refetchInterval: 5000,
    select: (data) => data.map(derivePollerDisplay),
  })
}

export type PollerAction = 'pause' | 'resume' | 'restart'

export function usePollerAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ api, action }: { api: string; action: PollerAction }) =>
      apiFetch(`/admin/pollers/${api}/${action}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pollers'] }),
  })
}
