import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import type { AuthUser } from './types'

export function useAuth() {
  return useQuery<AuthUser>({
    queryKey: ['me'],
    queryFn: () => apiFetch<AuthUser>('/auth/me'),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}
