import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PollerHealth, ProcessorHealth } from './types'
import {
  derivePollerDisplay,
  derivePollerState,
  deriveProcessorDisplay,
  deriveProcessorState,
  formatAgo,
  formatDateTime,
} from './utils'

const NOW = 1748515200

beforeEach(() => {
  vi.spyOn(Date, 'now').mockReturnValue(NOW * 1000)
})

const poller: PollerHealth = {
  api: 'corp_ann',
  module: 'engine.pollers.corp_ann',
  heartbeat: String(NOW - 2),
  last_success: String(NOW - 2),
  status: 'running',
  error_count: 0,
  interval: 5,
  enabled: true,
}

describe('derivePollerState', () => {
  it('returns running when healthy', () => expect(derivePollerState(poller)).toBe('running'))
  it('returns disabled when not enabled', () =>
    expect(derivePollerState({ ...poller, enabled: false })).toBe('disabled'))
  it('returns paused when status is paused', () =>
    expect(derivePollerState({ ...poller, status: 'paused' })).toBe('paused'))
  it('returns warn when error_count > 0 but < 10', () =>
    expect(derivePollerState({ ...poller, error_count: 3 })).toBe('warn'))
  it('returns crit when error_count >= 10', () =>
    expect(derivePollerState({ ...poller, error_count: 10 })).toBe('crit'))
  it('returns crit when heartbeat is null', () =>
    expect(derivePollerState({ ...poller, heartbeat: null })).toBe('crit'))
})

describe('derivePollerDisplay', () => {
  it('uses module as subtitle and poller kind', () => {
    const display = derivePollerDisplay(poller)
    expect(display.subtitle).toBe('engine.pollers.corp_ann')
    expect(display.kind).toBe('poller')
    expect(display.name).toBe('corp_ann')
  })
})

const processor: ProcessorHealth = {
  api: 'corp_ann',
  module: 'engine.processors.corp_ann',
  status: 'running',
  queue_size: 12,
  enabled: true,
  config: { pool_size: 8 },
  pollers: ['corp_ann'],
}

describe('deriveProcessorState', () => {
  it('returns running when enabled and running', () =>
    expect(deriveProcessorState(processor)).toBe('running'))
  it('returns disabled when not enabled', () =>
    expect(deriveProcessorState({ ...processor, enabled: false })).toBe('disabled'))
  it('returns paused when status is paused', () =>
    expect(deriveProcessorState({ ...processor, status: 'paused' })).toBe('paused'))
  it('returns crit when enabled but status unknown', () =>
    expect(deriveProcessorState({ ...processor, status: 'unknown' })).toBe('crit'))
})

describe('deriveProcessorDisplay', () => {
  it('exposes pool size, linked pollers, and metrics', () => {
    const display = deriveProcessorDisplay(processor)
    expect(display.poolSize).toBe(8)
    expect(display.pollers).toEqual(['corp_ann'])
    expect(display.metrics.find((metric) => metric.label === 'Workers')?.value).toBe('8')
    expect(display.metrics.find((metric) => metric.label === 'Queue depth')?.value).toBe('12')
  })

  it('defaults pool size to 1 when config omits it', () => {
    const display = deriveProcessorDisplay({ ...processor, config: {} })
    expect(display.poolSize).toBe(1)
  })
})

describe('formatAgo', () => {
  it('returns — for null', () => expect(formatAgo(null)).toBe('—'))
  it('formats seconds', () => expect(formatAgo(String(NOW - 30))).toBe('30s ago'))
  it('formats minutes and seconds', () => expect(formatAgo(String(NOW - 90))).toBe('1m 30s ago'))
  it('formats whole minutes', () => expect(formatAgo(String(NOW - 120))).toBe('2m ago'))
})

describe('formatDateTime', () => {
  it('returns — for null', () => expect(formatDateTime(null)).toBe('—'))
  it('returns — for a non-finite value', () => expect(formatDateTime('not-a-number')).toBe('—'))
  it('formats a unix-seconds timestamp as "D Mon YYYY, h:mmAM/PM"', () => {
    // Asserts the shape rather than an exact value to stay timezone-independent.
    expect(formatDateTime(NOW)).toMatch(/^\d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2}(AM|PM)$/)
  })
  it('accepts a numeric string', () => {
    expect(formatDateTime(String(NOW))).toMatch(/^\d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2}(AM|PM)$/)
  })
})
