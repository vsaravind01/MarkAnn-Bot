import { ComponentCard } from './ComponentCard'
import './engine.css'
import { usePollers } from './usePollers'
import { usePools } from './usePools'

export function ComponentsPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const { poolSizes, isError: poolsError } = usePools(pollers.map((p) => p.id))

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError || poolsError) return <div className="empty-state">Unable to load components right now.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Components</h2>
      </div>
      {pollers.length === 0 ? (
        <div className="empty-state">No components registered.</div>
      ) : (
        <div className="grid">
          {pollers.map((p) => (
            <ComponentCard key={p.id} poller={p} poolSize={poolSizes.get(p.poolSizeKey)} />
          ))}
        </div>
      )}
    </div>
  )
}
