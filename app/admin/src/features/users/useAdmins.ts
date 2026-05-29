import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import type { PaginatedUsers, UserOut } from './types'

const FETCH_PAGE_SIZE = 100

export function useAdmins(page = 1, pageSize = 20) {
  const query = useQuery<UserOut[]>({
    queryKey: ['admins'],
    queryFn: async () => {
      const first = await apiFetch<PaginatedUsers>(
        `/auth/admin/users?page=1&page_size=${FETCH_PAGE_SIZE}`,
      )
      const totalPages = Math.ceil(first.total / FETCH_PAGE_SIZE)

      const remainingPages = await Promise.all(
        Array.from({ length: Math.max(0, totalPages - 1) }, (_, index) =>
          apiFetch<PaginatedUsers>(
            `/auth/admin/users?page=${index + 2}&page_size=${FETCH_PAGE_SIZE}`,
          ),
        ),
      )

      const allUsers = [...first.items]
      for (const nextPage of remainingPages) {
        allUsers.push(...nextPage.items)
      }

      return allUsers.filter((u) => u.role !== 'trader')
    },
    refetchInterval: 30000,
  })

  const adminsOnly = query.data ?? []
  const start = (page - 1) * pageSize
  const end = start + pageSize

  return {
    ...query,
    data: query.data
      ? {
          items: adminsOnly.slice(start, end),
          total: adminsOnly.length,
          page,
          page_size: pageSize,
        }
      : undefined,
  }
}

export function useAdminPatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      apiFetch(`/auth/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admins'] }),
  })
}

export function useAdminCreate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { email: string; password: string; first_name: string; last_name: string }) =>
      apiFetch('/auth/admin/register', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admins'] }),
  })
}
