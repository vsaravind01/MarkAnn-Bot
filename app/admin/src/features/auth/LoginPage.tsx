import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiFetch } from '../../lib/api'
import { useAuth } from './useAuth'
import './auth.css'

export function LoginPage() {
  const { data: user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const from = location.state?.from as
    | { pathname?: string; search?: string; hash?: string }
    | undefined
  const nextPath =
    from?.pathname && !['/login', '/bootstrap'].includes(from.pathname)
      ? `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`
      : '/overview'

  const mutation = useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate(nextPath, { replace: true })
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Login failed')
    },
  })

  if (user) return <Navigate to={nextPath} replace />

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    mutation.mutate({ email, password })
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="9" fill="#0F141D" />
            <rect x="0.5" y="0.5" width="39" height="39" rx="8.5" stroke="#fff" strokeOpacity=".10" />
            <g stroke="#4F7CFF" strokeWidth="2.6" strokeLinecap="round">
              <path d="M11 27.5V21.5" />
              <path d="M18 30V14" />
              <path d="M25 24V10" />
            </g>
            <path
              d="M11 22 L18 16 L25 12 L31 8"
              stroke="#4F7CFF"
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="31" cy="8" r="2.6" fill="#4F7CFF" />
          </svg>
          <span className="auth-brand-name">
            Mark<span>Ann</span> <span className="auth-env">OPS</span>
          </span>
        </div>
        <h1 className="auth-title">Sign in</h1>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label className="field-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              className="field-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="field-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          {error && <p className="field-error">{error}</p>}
          <button type="submit" className="btn primary auth-submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="auth-footer">
          First time? <Link to="/bootstrap">Set up operator account →</Link>
        </p>
      </div>
    </div>
  )
}
