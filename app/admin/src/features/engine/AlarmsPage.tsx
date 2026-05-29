import { ComponentCard } from './ComponentCard'
import './engine.css'
import { usePollers } from './usePollers'
import { usePools } from './usePools'

export function AlarmsPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const alarms = pollers.filter((p) => p.state === 'crit' || p.state === 'warn')
  const { poolSizes, isError: poolsError } = usePools(alarms.map((p) => p.id))

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError || poolsError) return <div className="empty-state">Unable to load alarms right now.</div>

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
          {alarms.map((p) => (
            <ComponentCard key={p.id} poller={p} poolSize={poolSizes.get(p.poolSizeKey)} />
          ))}
        </div>
      )}
    </div>
  )
}
