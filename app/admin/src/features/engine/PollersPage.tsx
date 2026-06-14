import { StatePill } from '../../components/StatePill'
import { useToast } from '../shell/Toast'
import { ActionBar, type ComponentAction } from './components/ActionBar'
import { type Column, ComponentTable } from './components/ComponentTable'
import './engine.css'
import type { PollerDisplay } from './types'
import { usePollerAction, usePollers } from './usePollers'

const PAST = { pause: 'paused', resume: 'resumed', restart: 'restarted' } as const

export function PollersPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const action = usePollerAction()
  const toast = useToast()

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load pollers right now.</div>

  function fire(poller: PollerDisplay, next: ComponentAction) {
    action.mutate(
      { api: poller.id, action: next },
      {
        onSuccess: () => toast.success(`${poller.name} ${PAST[next]}`),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  const metricLabels = pollers[0]?.metrics.map((metric) => metric.label) ?? []
  const columns: Column<PollerDisplay>[] = [
    { key: 'name', header: 'Name', render: (poller) => poller.name, className: 'num' },
    { key: 'type', header: 'Type', render: (poller) => poller.subtitle },
    { key: 'state', header: 'State', render: (poller) => <StatePill state={poller.state} /> },
    ...metricLabels.map((label) => ({
      key: `m:${label}`,
      header: label,
      className: 'num',
      render: (poller: PollerDisplay) => {
        const metric = poller.metrics.find((item) => item.label === label)
        return <span className={metric?.tone}>{metric?.value ?? '—'}</span>
      },
    })),
    {
      key: 'actions',
      header: 'Actions',
      render: (poller) => (
        <ActionBar name={poller.name} state={poller.state} onAction={(next) => fire(poller, next)} />
      ),
    },
  ]

  return (
    <div>
      <div className="page-head">
        <h2>Pollers</h2>
      </div>
      <ComponentTable
        columns={columns}
        rows={pollers}
        rowKey={(poller) => poller.id}
        empty="No pollers registered."
      />
    </div>
  )
}
