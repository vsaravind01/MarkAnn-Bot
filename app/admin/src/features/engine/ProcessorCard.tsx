import { useToast } from '../shell/Toast'
import { ActionBar, type ComponentAction } from './components/ActionBar'
import { CardShell } from './components/CardShell'
import { MetricGrid } from './components/MetricGrid'
import { Stepper } from './components/Stepper'
import type { ProcessorDisplay } from './types'
import { useProcessorAction, useProcessorResize } from './useProcessors'

const PAST = { pause: 'paused', resume: 'resumed', restart: 'restarted' } as const

export function ProcessorCard({ processor }: { processor: ProcessorDisplay }) {
  const action = useProcessorAction()
  const resize = useProcessorResize()
  const toast = useToast()

  function onAction(next: ComponentAction) {
    action.mutate(
      { api: processor.id, action: next },
      {
        onSuccess: () => toast.success(`${processor.name} ${PAST[next]}`),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  function onResize(next: number) {
    resize.mutate(
      { api: processor.id, poolSize: next },
      {
        onSuccess: () =>
          toast.success(
            `${processor.name} workers → ${next} (applies on next start; Force-restart to apply now)`,
          ),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  return (
    <CardShell
      kind="processor"
      name={processor.name}
      subtitle={processor.subtitle}
      state={processor.state}
    >
      <MetricGrid metrics={processor.metrics} />
      <div className="pool">
        <span className="lab">Pool size</span>
        <Stepper
          value={processor.poolSize}
          disabled={resize.isPending || processor.state === 'disabled'}
          onChange={onResize}
          label={`pool size for ${processor.name}`}
        />
        <span className="lab" style={{ marginLeft: 'auto' }} title="Applies on restart">
          applies on restart
        </span>
      </div>
      <ActionBar name={processor.name} state={processor.state} onAction={onAction} />
    </CardShell>
  )
}
