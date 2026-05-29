import { useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { StatePill } from '../../components/StatePill'
import { useToast } from '../shell/Toast'
import './engine.css'
import type { PollerDisplay } from './types'
import { usePollerAction, usePollers, type PollerAction } from './usePollers'

export function PollersPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const pollerAction = usePollerAction()
  const toast = useToast()
  const [confirm, setConfirm] = useState<{ poller: PollerDisplay; action: PollerAction } | null>(null)

  function fireAction(poller: PollerDisplay, action: PollerAction) {
    if (action === 'restart') {
      setConfirm({ poller, action })
      return
    }
    if (action === 'pause') {
      setConfirm({ poller, action })
      return
    }
    pollerAction.mutate(
      { api: poller.id, action },
      {
        onSuccess: () => toast.success(`${poller.name} resumed`),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load pollers right now.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Pollers</h2>
      </div>
      {pollers.length === 0 ? (
        <div className="empty-state">No pollers registered.</div>
      ) : (
        <table className="engine-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>State</th>
              {pollers[0]?.metrics.map((m) => <th key={m.label}>{m.label}</th>)}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {pollers.map((p) => (
              <tr key={p.id}>
                <td className="num">{p.name}</td>
                <td>{p.type}</td>
                <td>
                  <StatePill state={p.state} />
                </td>
                {p.metrics.map((m) => (
                  <td key={m.label} className={`num${m.tone ? ` ${m.tone}` : ''}`}>
                    {m.value}
                  </td>
                ))}
                <td>
                  <div className="actions">
                    {p.state === 'paused' ? (
                      <button className="btn secondary" onClick={() => fireAction(p, 'resume')}>
                        Resume
                      </button>
                    ) : (
                      <button className="btn secondary" onClick={() => fireAction(p, 'pause')}>
                        Pause
                      </button>
                    )}
                    <button className="btn danger" onClick={() => fireAction(p, 'restart')}>
                      Force-restart
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {confirm &&
        (confirm.action === 'restart' ? (
          <ConfirmDialog
            open
            variant="type-to-confirm"
            confirmWord={confirm.poller.name}
            title="Force-restart component?"
            description={`Force-restarts ${confirm.poller.name}. In-flight messages will be dropped.`}
            confirmLabel="Force-restart"
            danger
            onConfirm={() =>
              pollerAction.mutate(
                { api: confirm.poller.id, action: 'restart' },
                {
                  onSuccess: () => toast.success(`${confirm.poller.name} restarted`),
                  onError: (e) => toast.error(e.message),
                },
              )
            }
            onOpenChange={(o) => {
              if (!o) setConfirm(null)
            }}
          />
        ) : (
          <ConfirmDialog
            open
            title="Pause component?"
            description={`Pauses ${confirm.poller.name}. Backlog may grow while paused.`}
            confirmLabel="Pause"
            onConfirm={() =>
              pollerAction.mutate(
                { api: confirm.poller.id, action: 'pause' },
                {
                  onSuccess: () => toast.success(`${confirm.poller.name} paused`),
                  onError: (e) => toast.error(e.message),
                },
              )
            }
            onOpenChange={(o) => {
              if (!o) setConfirm(null)
            }}
          />
        ))}
    </div>
  )
}
