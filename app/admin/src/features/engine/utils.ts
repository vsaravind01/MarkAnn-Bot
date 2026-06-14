import type { ComponentState } from '../../components/StatePill'
import type { Metric, PollerDisplay, PollerHealth, ProcessorDisplay, ProcessorHealth } from './types'

export function derivePollerState(h: PollerHealth): ComponentState {
  if (!h.enabled) return 'disabled'
  if (h.status === 'paused') return 'paused'
  if (h.heartbeat === null || h.error_count >= 10) return 'crit'
  if (h.error_count > 0) return 'warn'
  return 'running'
}

export function deriveProcessorState(h: ProcessorHealth): ComponentState {
  if (!h.enabled) return 'disabled'
  if (h.status === 'paused') return 'paused'
  if (h.status === 'running') return 'running'
  return 'crit'
}

export function formatAgo(ts: string | null): string {
  if (!ts) return '—'
  const diff = Math.floor(Date.now() / 1000) - parseInt(ts, 10)
  if (diff < 0) return 'just now'
  if (diff < 60) return `${diff}s ago`
  const m = Math.floor(diff / 60)
  const s = diff % 60
  return s > 0 ? `${m}m ${s}s ago` : `${m}m ago`
}

export function derivePollerDisplay(h: PollerHealth): PollerDisplay {
  const state = derivePollerState(h)
  const metrics: Metric[] = [
    {
      label: 'Errors',
      value: String(h.error_count),
      tone: h.error_count >= 10 ? 'crit' : h.error_count > 0 ? 'warn' : undefined,
    },
    {
      label: 'Last poll',
      value: formatAgo(h.last_success),
      tone: state === 'crit' ? 'crit' : undefined,
    },
    {
      label: 'Heartbeat',
      value: h.heartbeat !== null ? 'OK' : 'MISSING',
      tone: h.heartbeat === null ? 'crit' : undefined,
    },
    { label: 'Interval', value: `${h.interval}s` },
  ]

  return {
    id: h.api,
    name: h.api,
    subtitle: h.module,
    kind: 'poller',
    state,
    metrics,
  }
}

export function deriveProcessorDisplay(h: ProcessorHealth): ProcessorDisplay {
  const state = deriveProcessorState(h)
  const poolSize = h.config?.pool_size ?? 1
  const metrics: Metric[] = [
    { label: 'Queue depth', value: String(h.queue_size) },
    { label: 'Workers', value: String(poolSize) },
    { label: 'Pollers', value: h.pollers.join(', ') || '—' },
  ]

  return {
    id: h.api,
    name: h.api,
    subtitle: h.module,
    kind: 'processor',
    state,
    poolSize,
    pollers: h.pollers,
    metrics,
  }
}
