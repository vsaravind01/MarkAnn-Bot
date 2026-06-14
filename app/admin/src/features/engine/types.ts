import type { ComponentState } from '../../components/StatePill'

export type ComponentKind = 'poller' | 'processor'

export interface Metric {
  label: string
  value: string
  tone?: 'warn' | 'crit'
}

export interface ComponentDisplay {
  id: string
  name: string
  subtitle: string
  kind: ComponentKind
  state: ComponentState
  metrics: Metric[]
}

export interface PollerHealth {
  api: string
  module: string
  heartbeat: string | null
  last_success: string | null
  status: string
  error_count: number
  interval: number
  enabled: boolean
}

export interface ProcessorHealth {
  api: string
  module: string
  status: string
  queue_size: number
  enabled: boolean
  config: { pool_size?: number } & Record<string, unknown>
  pollers: string[]
}

export type PollerDisplay = ComponentDisplay & { kind: 'poller' }

export interface ProcessorDisplay extends ComponentDisplay {
  kind: 'processor'
  poolSize: number
  pollers: string[]
}
