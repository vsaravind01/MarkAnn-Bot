import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'

export interface LogEntry {
  ts: number
  lvl: 'ok' | 'warn' | 'crit' | 'info'
  msg: string
  api?: string
}

export function useEvents() {
  return useQuery<LogEntry[]>({
    queryKey: ['events'],
    queryFn: () => apiFetch<LogEntry[]>('/admin/events'),
    refetchInterval: 5000,
  })
}
