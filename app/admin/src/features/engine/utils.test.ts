import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PollerHealth } from './types'
import { derivePollerState, formatAgo } from './utils'

const NOW = 1748515200

beforeEach(() => {
  vi.spyOn(Date, 'now').mockReturnValue(NOW * 1000)
})

const base: PollerHealth = {
  api: 'corp_ann',
  heartbeat: String(NOW - 2),
  last_success: String(NOW - 2),
  status: 'running',
  error_count: 0,
  interval: 5,
}

describe('derivePollerState', () => {
  it('returns running when healthy', () => expect(derivePollerState(base)).toBe('running'))
  it('returns paused when status is paused', () =>
    expect(derivePollerState({ ...base, status: 'paused' })).toBe('paused'))
  it('returns warn when error_count > 0 but < 10', () =>
    expect(derivePollerState({ ...base, error_count: 3 })).toBe('warn'))
  it('returns crit when error_count >= 10', () =>
    expect(derivePollerState({ ...base, error_count: 10 })).toBe('crit'))
  it('returns crit when heartbeat is null', () =>
    expect(derivePollerState({ ...base, heartbeat: null })).toBe('crit'))
})

describe('formatAgo', () => {
  it('returns — for null', () => expect(formatAgo(null)).toBe('—'))
  it('formats seconds', () => expect(formatAgo(String(NOW - 30))).toBe('30s ago'))
  it('formats minutes and seconds', () => expect(formatAgo(String(NOW - 90))).toBe('1m 30s ago'))
  it('formats whole minutes', () => expect(formatAgo(String(NOW - 120))).toBe('2m ago'))
})
