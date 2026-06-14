import { useToast } from '../shell/Toast'
import { ActionBar, type ComponentAction } from './components/ActionBar'
import { CardShell } from './components/CardShell'
import { MetricGrid } from './components/MetricGrid'
import type { PollerDisplay } from './types'
import { usePollerAction } from './usePollers'

const PAST = { pause: 'paused', resume: 'resumed', restart: 'restarted' } as const

export function PollerCard({ poller }: { poller: PollerDisplay }) {
  const action = usePollerAction()
  const toast = useToast()

  function onAction(next: ComponentAction) {
    action.mutate(
      { api: poller.id, action: next },
      {
        onSuccess: () => toast.success(`${poller.name} ${PAST[next]}`),
        onError: (error: Error) => toast.error(error.message),
      },
    )
  }

  return (
    <CardShell kind="poller" name={poller.name} subtitle={poller.subtitle} state={poller.state}>
      <MetricGrid metrics={poller.metrics} />
      <ActionBar name={poller.name} state={poller.state} onAction={onAction} />
    </CardShell>
  )
}
