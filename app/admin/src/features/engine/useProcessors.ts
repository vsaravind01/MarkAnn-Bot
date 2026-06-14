import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import type { ProcessorDisplay, ProcessorHealth } from './types'
import { deriveProcessorDisplay } from './utils'

export function useProcessors() {
  return useQuery<ProcessorHealth[], Error, ProcessorDisplay[]>({
    queryKey: ['processors'],
    queryFn: () => apiFetch<ProcessorHealth[]>('/admin/processors'),
    refetchInterval: 5000,
    select: (data) => data.map(deriveProcessorDisplay),
  })
}

export type ProcessorAction = 'pause' | 'resume' | 'restart'

export function useProcessorAction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ api, action }: { api: string; action: ProcessorAction }) =>
      apiFetch(`/admin/processors/${api}/${action}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['processors'] }),
  })
}

export function useProcessorResize() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ api, poolSize }: { api: string; poolSize: number }) =>
      apiFetch(`/admin/processors/${api}`, {
        method: 'PATCH',
        body: JSON.stringify({ pool_size: poolSize }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['processors'] }),
  })
}
