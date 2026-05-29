import * as Dialog from '@radix-ui/react-dialog'
import { type FormEvent, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Pagination } from '../../components/Pagination'
import { ApiError } from '../../lib/api'
import { useToast } from '../shell/Toast'
import type { UserOut } from './types'
import './users.css'
import { useAdminCreate, useAdminPatch, useAdmins } from './useAdmins'

function StatusBadge({ active }: { active: boolean }) {
  return <span className={`status-badge ${active ? 'status-active' : 'status-inactive'}`}>{active ? 'Active' : 'Inactive'}</span>
}

function RoleBadge({ role }: { role: string }) {
  const cls = role === 'superuser' ? 'role-badge-super' : 'role-badge-admin'
  return <span className={`status-badge ${cls}`}>{role}</span>
}

function formatDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function parsePageParam(raw: string | null): number {
  const parsed = Number(raw ?? '1')
  return Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : 1
}

function CreateAdminDialog({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const create = useAdminCreate()
  const [form, setForm] = useState({ email: '', password: '', first_name: '', last_name: '' })
  const [emailError, setEmailError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setEmailError(null)
    create.mutate(form, {
      onSuccess: () => {
        toast.success('Admin account created')
        onClose()
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409) {
          setEmailError('This email is already registered')
        } else {
          toast.error(err instanceof ApiError ? err.message : 'Failed to create admin')
        }
      },
    })
  }

  return (
    <Dialog.Root
      open
      onOpenChange={(o) => {
        if (!o) onClose()
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="scrim" />
        <Dialog.Content className="modal">
          <div className="modal-head">
            <Dialog.Title className="modal-title">Create admin account</Dialog.Title>
            <Dialog.Description className="sr-only">
              Create a new admin user account.
            </Dialog.Description>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="create-admin-form">
              <div className="name-row">
                <div className="field">
                  <label className="field-label" htmlFor="ca-first">
                    First name
                  </label>
                  <input
                    id="ca-first"
                    type="text"
                    className="field-input"
                    required
                    autoFocus
                    value={form.first_name}
                    onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="ca-last">
                    Last name
                  </label>
                  <input
                    id="ca-last"
                    type="text"
                    className="field-input"
                    required
                    value={form.last_name}
                    onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                  />
                </div>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="ca-email">
                  Email
                </label>
                <input
                  id="ca-email"
                  type="email"
                  className="field-input"
                  required
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                />
                {emailError && <span className="field-error">{emailError}</span>}
              </div>
              <div className="field">
                <label className="field-label" htmlFor="ca-pass">
                  Password
                </label>
                <input
                  id="ca-pass"
                  type="password"
                  className="field-input"
                  required
                  minLength={8}
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                />
              </div>
            </div>
            <div className="modal-foot">
              <button type="button" className="btn ghost" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn primary" disabled={create.isPending}>
                {create.isPending ? 'Creating…' : 'Create account'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function AdminsPage() {
  const [params] = useSearchParams()
  const page = parsePageParam(params.get('page'))
  const { data, isLoading, isError } = useAdmins(page)
  const patch = useAdminPatch()
  const toast = useToast()
  const [disabling, setDisabling] = useState<UserOut | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  if (isLoading) return <div className="loading-screen">Loading admins…</div>
  if (isError) return <div className="empty-state">Unable to load admins right now.</div>

  const items = data?.items ?? []

  return (
    <div>
      <div className="page-head">
        <h2>Admins</h2>
        <span className="page-sub">{data?.total ?? 0} total</span>
        <div className="page-actions">
          <button className="btn primary" onClick={() => setShowCreate(true)}>
            Create admin
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">No admin accounts yet.</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.first_name} {u.last_name}
                  </td>
                  <td className="num">{u.email}</td>
                  <td>
                    <RoleBadge role={u.role} />
                  </td>
                  <td>
                    <StatusBadge active={u.is_active} />
                  </td>
                  <td className="num">{formatDate(u.created_at)}</td>
                  <td>
                    {u.role !== 'superuser' &&
                      (u.is_active ? (
                        <button className="btn danger" onClick={() => setDisabling(u)}>
                          Disable
                        </button>
                      ) : (
                        <button
                          className="btn secondary"
                          onClick={() =>
                            patch.mutate(
                              { id: u.id, is_active: true },
                              {
                                onSuccess: () => toast.success(`${u.email} enabled`),
                                onError: (e) => toast.error(e.message),
                              },
                            )
                          }
                        >
                          Enable
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination total={data?.total ?? 0} pageSize={data?.page_size ?? 20} />
        </>
      )}

      {disabling && (
        <ConfirmDialog
          open
          title="Disable this admin?"
          description={`${disabling.email} will be signed out and cannot log in until re-enabled.`}
          confirmLabel="Disable"
          danger
          onConfirm={() =>
            patch.mutate(
              { id: disabling.id, is_active: false },
              {
                onSuccess: () => toast.success(`${disabling.email} disabled`),
                onError: (e) => toast.error(e.message),
              },
            )
          }
          onOpenChange={(o) => {
            if (!o) setDisabling(null)
          }}
        />
      )}

      {showCreate && <CreateAdminDialog onClose={() => setShowCreate(false)} />}
    </div>
  )
}
