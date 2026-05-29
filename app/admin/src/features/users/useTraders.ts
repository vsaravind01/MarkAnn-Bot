import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import type { PaginatedUsers } from './types'

export function useTraders(page = 1, pageSize = 20) {
  return useQuery<PaginatedUsers>({
    queryKey: ['traders', page, pageSize],
    queryFn: () => apiFetch<PaginatedUsers>(`/auth/admin/traders?page=${page}&page_size=${pageSize}`),
    refetchInterval: 30000,
  })
}

export function useTraderPatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      apiFetch(`/auth/admin/traders/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['traders'] }),
  })
}
