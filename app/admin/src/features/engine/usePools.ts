import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiFetch } from '../../lib/api'

interface PoolSize {
  api: string
  size: number
}

export function usePools(apis: string[]) {
  return useQueries({
    queries: apis.map((api) => ({
      queryKey: ['pools', api],
      queryFn: async (): Promise<PoolSize | null> => {
        try {
          return await apiFetch<PoolSize>(`/admin/pools/${api}`)
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            return null
          }

          throw error
        }
      },
      retry: false,
      refetchInterval: 5000,
    })),
    combine: (results) => {
      const map = new Map<string, number>()
      apis.forEach((api, i) => {
        const data = results[i].data
        if (data) map.set(api, data.size)
      })
      return {
        poolSizes: map,
        isLoading: results.some((r) => r.isLoading),
        isError: results.some((r) => r.isError),
      }
    },
  })
}

export function usePoolResize() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ api, size }: { api: string; size: number }) =>
      apiFetch(`/admin/pools/${api}`, { method: 'PATCH', body: JSON.stringify({ size }) }),
    onSuccess: (_, { api }) => queryClient.invalidateQueries({ queryKey: ['pools', api] }),
  })
}
