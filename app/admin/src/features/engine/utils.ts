import type { ComponentState } from '../../components/StatePill'
import type { PollerDisplay, PollerHealth } from './types'

const API_META: Record<string, { type: string; icon: string }> = {
  corp_ann: { type: 'NSE announcement poller', icon: 'radio' },
}

export function derivePollerState(h: PollerHealth): ComponentState {
  if (h.status === 'paused') return 'paused'
  if (h.heartbeat === null || h.error_count >= 10) return 'crit'
  if (h.error_count > 0) return 'warn'
  return 'running'
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
  const meta = API_META[h.api] ?? { type: h.api, icon: 'server' }
  return {
    id: h.api,
    name: h.api,
    type: meta.type,
    icon: meta.icon,
    state,
    poolSizeKey: h.api,
    metrics: [
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
    ],
  }
}
