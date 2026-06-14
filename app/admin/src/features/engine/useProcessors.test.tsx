import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useProcessors } from './useProcessors'

const mockFetch = vi.fn()

beforeEach(() => vi.stubGlobal('fetch', mockFetch))

afterEach(() => {
  vi.unstubAllGlobals()
  mockFetch.mockReset()
})

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useProcessors', () => {
  it('maps processor health into display objects', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: 'OK',
      headers: { get: () => 'application/json' },
      json: () =>
        Promise.resolve([
          {
            api: 'corp_ann',
            module: 'engine.processors.corp_ann',
            status: 'running',
            queue_size: 3,
            enabled: true,
            config: { pool_size: 8 },
            pollers: ['corp_ann'],
          },
        ]),
    })

    const { result } = renderHook(() => useProcessors(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.[0].poolSize).toBe(8)
    expect(result.current.data?.[0].kind).toBe('processor')
  })
})
