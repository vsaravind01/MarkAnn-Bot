import { PollerCard } from './PollerCard'
import './engine.css'
import { usePollers } from './usePollers'

export function AlarmsPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const alarms = pollers.filter((poller) => poller.state === 'crit' || poller.state === 'warn')

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load alarms right now.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Alarms</h2>
        <span className="page-sub">{alarms.length} active</span>
      </div>
      {alarms.length === 0 ? (
        <div className="empty-state">No active alarms. All components nominal.</div>
      ) : (
        <div className="grid">
          {alarms.map((poller) => (
            <PollerCard key={poller.id} poller={poller} />
          ))}
        </div>
      )}
    </div>
  )
}
