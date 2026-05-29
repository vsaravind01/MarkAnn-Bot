import type { ComponentState } from '../../components/StatePill'

export interface PollerHealth {
  api: string
  heartbeat: string | null
  last_success: string | null
  status: string
  error_count: number
  interval: number
}

export interface PollerDisplay {
  id: string
  name: string
  type: string
  icon: string
  state: ComponentState
  metrics: Array<{ label: string; value: string; tone?: 'warn' | 'crit' }>
  poolSizeKey: string
}
