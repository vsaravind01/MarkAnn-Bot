import { useToast } from '../shell/Toast'
import './engine.css'
import { usePollers } from './usePollers'
import { usePoolResize, usePools } from './usePools'

export function PoolsPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const apis = pollers.map((p) => p.id)
  const { poolSizes, isLoading: poolsLoading, isError: poolsError } = usePools(apis)
  const poolResize = usePoolResize()
  const toast = useToast()

  if (isLoading || poolsLoading) return <div className="loading-screen">Loading…</div>
  if (isError || poolsError) return <div className="empty-state">Unable to load worker pools right now.</div>

  const poolEntries = apis.filter((api) => poolSizes.has(api))

  return (
    <div>
      <div className="page-head">
        <h2>Worker pools</h2>
      </div>
      {poolEntries.length === 0 ? (
        <div className="empty-state">No worker pools configured.</div>
      ) : (
        <table className="engine-table">
          <thead>
            <tr>
              <th>Pool</th>
              <th>Current size</th>
              <th>Resize</th>
            </tr>
          </thead>
          <tbody>
            {poolEntries.map((api) => {
              const size = poolSizes.get(api) ?? 1
              return (
                <tr key={api}>
                  <td className="num">{api}</td>
                  <td className="num">{size} workers</td>
                  <td>
                    <div className="stepper">
                      <button
                        aria-label={`Decrease pool size for ${api}`}
                        disabled={poolResize.isPending}
                        onClick={() =>
                          poolResize.mutate(
                            { api, size: Math.max(1, size - 1) },
                            { onError: (e) => toast.error(e.message) },
                          )
                        }
                      >
                        −
                      </button>
                      <span className="val num">{size}</span>
                      <button
                        aria-label={`Increase pool size for ${api}`}
                        disabled={poolResize.isPending}
                        onClick={() =>
                          poolResize.mutate(
                            { api, size: Math.min(64, size + 1) },
                            { onError: (e) => toast.error(e.message) },
                          )
                        }
                      >
                        +
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
