let _refreshPromise: Promise<void> | null = null

function normalizeHeaders(headers: RequestInit['headers']): Headers {
  if (!headers) return new Headers()
  return new Headers(headers)
}

function shouldSetJsonContentType(body: BodyInit | null | undefined): boolean {
  if (body == null) return false
  if (typeof body === 'string') return true
  if (body instanceof FormData) return false
  if (body instanceof URLSearchParams) return false
  if (body instanceof Blob) return false
  if (body instanceof ArrayBuffer) return false
  if (ArrayBuffer.isView(body)) return false
  if (typeof ReadableStream !== 'undefined' && body instanceof ReadableStream) return false
  return true
}

async function doRefresh(): Promise<void> {
  const res = await fetch('/auth/refresh', { method: 'POST', credentials: 'include' })
  if (!res.ok) {
    const { pathname } = window.location
    if (pathname !== '/login' && pathname !== '/bootstrap') {
      window.location.href = '/login'
    }
    throw new ApiError(401, 'Session expired')
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = normalizeHeaders(init.headers)
  if (!headers.has('content-type') && shouldSetJsonContentType(init.body)) {
    headers.set('Content-Type', 'application/json')
  }

  const opts: RequestInit = {
    ...init,
    credentials: 'include',
    headers,
  }

  let res = await fetch(path, opts)

  if (res.status === 401) {
    if (!_refreshPromise) {
      _refreshPromise = doRefresh().finally(() => { _refreshPromise = null })
    }
    await _refreshPromise
    res = await fetch(path, opts)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, (body as { detail?: string }).detail ?? res.statusText)
  }

  const ct = res.headers.get('content-type') ?? ''
  if (ct.includes('application/json')) return res.json() as Promise<T>
  return undefined as T
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}
