import { StatePill } from '../../components/StatePill'
import { useToast } from '../shell/Toast'
import { ActionBar, type ComponentAction } from './components/ActionBar'
import { type Column, ComponentTable } from './components/ComponentTable'
import { Stepper } from './components/Stepper'
import './engine.css'
import type { ProcessorDisplay } from './types'
import { useProcessorAction, useProcessorResize, useProcessors } from './useProcessors'

const PAST = { pause: 'paused', resume: 'resumed', restart: 'restarted' } as const

export function ProcessorsPage() {
  const { data: processors = [], isLoading, isError } = useProcessors()
  const action = useProcessorAction()
  const resize = useProcessorResize()
  const toast = useToast()

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load processors right now.</div>

  function fire(processor: ProcessorDisplay, next: ComponentAction) {
    action.mutate(
      { api: processor.id, action: next },
      {
        onSuccess: () => toast.success(`${processor.name} ${PAST[next]}`),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  function fireResize(processor: ProcessorDisplay, next: number) {
    resize.mutate(
      { api: processor.id, poolSize: next },
      {
        onSuccess: () =>
          toast.success(
            `${processor.name} workers -> ${next} (applies on next start; Force-restart to apply now)`,
          ),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  const columns: Column<ProcessorDisplay>[] = [
    { key: 'name', header: 'Name', render: (processor) => processor.name, className: 'num' },
    { key: 'type', header: 'Type', render: (processor) => processor.subtitle },
    {
      key: 'state',
      header: 'State',
      render: (processor) => <StatePill state={processor.state} />,
    },
    {
      key: 'queue',
      header: 'Queue depth',
      className: 'num',
      render: (processor) =>
        processor.metrics.find((metric) => metric.label === 'Queue depth')?.value ?? '—',
    },
    {
      key: 'workers',
      header: 'Workers',
      render: (processor) => (
        <Stepper
          value={processor.poolSize}
          disabled={resize.isPending}
          onChange={(next) => fireResize(processor, next)}
          label={`workers for ${processor.name}`}
        />
      ),
    },
    { key: 'pollers', header: 'Pollers', render: (processor) => processor.pollers.join(', ') || '—' },
    {
      key: 'actions',
      header: 'Actions',
      render: (processor) => (
        <ActionBar name={processor.name} state={processor.state} onAction={(next) => fire(processor, next)} />
      ),
    },
  ]

  return (
    <div>
      <div className="page-head">
        <h2>Processors</h2>
      </div>
      <ComponentTable
        columns={columns}
        rows={processors}
        rowKey={(processor) => processor.id}
        empty="No processors registered."
      />
    </div>
  )
}
