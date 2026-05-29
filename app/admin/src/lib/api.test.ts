import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch } from './api'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
})
afterEach(() => {
  vi.unstubAllGlobals()
  mockFetch.mockReset()
})

function mockResponse(status: number, body: unknown, contentType = 'application/json') {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    headers: { get: (h: string) => h === 'content-type' ? contentType : null },
    json: () => Promise.resolve(body),
  }
}

describe('apiFetch', () => {
  it('returns JSON on 200', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { data: 'hello' }))
    const result = await apiFetch<{ data: string }>('/test')
    expect(result).toEqual({ data: 'hello' })
    expect(mockFetch).toHaveBeenCalledWith('/test', expect.objectContaining({ credentials: 'include' }))
  })

  it('throws ApiError with status and message on 4xx', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(422, { detail: 'Invalid input' }))
    await expect(apiFetch('/test')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'Invalid input',
    })
  })

  it('on 401 fires refresh then retries', async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(401, {}))                  // original — 401
      .mockResolvedValueOnce(mockResponse(200, {}))                  // refresh call
      .mockResolvedValueOnce(mockResponse(200, { ok: true }))        // retry
    const result = await apiFetch<{ ok: boolean }>('/test')
    expect(result).toEqual({ ok: true })
    expect(mockFetch).toHaveBeenCalledTimes(3)
  })
})
