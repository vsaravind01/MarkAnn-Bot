import { type FormEvent, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiFetch } from '../../lib/api'
import { useAuth } from './useAuth'
import './auth.css'

export function BootstrapPage() {
  const { data: user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ email: '', password: '', first_name: '', last_name: '' })
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (body: typeof form) =>
      apiFetch('/auth/admin/register', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate('/overview')
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 403) {
        setError('A superuser already exists. Log in instead.')
      } else {
        setError(err instanceof ApiError ? err.message : 'Registration failed')
      }
    },
  })

  if (user) return <Navigate to="/overview" replace />

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    mutation.mutate(form)
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
        <h1 className="auth-title">Create operator account</h1>
        <p className="auth-desc">The first account becomes the superuser.</p>
        <form onSubmit={handleSubmit} className="auth-form">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="field">
              <label className="field-label" htmlFor="first_name">
                First name
              </label>
              <input
                id="first_name"
                type="text"
                className="field-input"
                value={form.first_name}
                onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                required
                autoFocus
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="last_name">
                Last name
              </label>
              <input
                id="last_name"
                type="text"
                className="field-input"
                value={form.last_name}
                onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                required
              />
            </div>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              className="field-input"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
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
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          {error && <p className="field-error">{error}</p>}
          <button type="submit" className="btn primary auth-submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="auth-footer">
          <Link to="/login">← Back to sign in</Link>
        </p>
      </div>
    </div>
  )
}
