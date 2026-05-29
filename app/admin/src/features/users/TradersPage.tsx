import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Pagination } from '../../components/Pagination'
import { useToast } from '../shell/Toast'
import type { UserOut } from './types'
import './users.css'
import { useTraderPatch, useTraders } from './useTraders'

function StatusBadge({ active }: { active: boolean }) {
  return <span className={`status-badge ${active ? 'status-active' : 'status-inactive'}`}>{active ? 'Active' : 'Inactive'}</span>
}

function formatDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function parsePageParam(raw: string | null): number {
  const parsed = Number(raw ?? '1')
  return Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : 1
}

export function TradersPage() {
  const [params] = useSearchParams()
  const page = parsePageParam(params.get('page'))
  const { data, isLoading, isError } = useTraders(page)
  const patch = useTraderPatch()
  const toast = useToast()
  const [disabling, setDisabling] = useState<UserOut | null>(null)

  if (isLoading) return <div className="loading-screen">Loading traders…</div>
  if (isError) return <div className="empty-state">Unable to load traders right now.</div>

  const items = data?.items ?? []

  return (
    <div>
      <div className="page-head">
        <h2>Traders</h2>
        <span className="page-sub">{data?.total ?? 0} total</span>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">No traders registered yet.</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Status</th>
                <th>Joined</th>
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
                    <StatusBadge active={u.is_active} />
                  </td>
                  <td className="num">{formatDate(u.created_at)}</td>
                  <td>
                    {u.is_active ? (
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
                    )}
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
          title="Disable this trader?"
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
    </div>
  )
}
