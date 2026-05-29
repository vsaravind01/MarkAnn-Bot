import './engine.css'
import { usePollers } from './usePollers'

interface LogEntry {
  ts: string
  lvl: 'info' | 'warn' | 'crit' | 'ok'
  msg: string
}

export function EventLogPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  // The health endpoint may return log data in the future; for now it does not.
  const log: LogEntry[] = (pollers as unknown as Array<{ log?: LogEntry[] }>)
    .flatMap((p) => p.log ?? [])
    .sort((a, b) => b.ts.localeCompare(a.ts))

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load the event log right now.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Event log</h2>
      </div>
      {log.length === 0 ? (
        <div className="empty-state">No log entries yet. The engine will write events here once started.</div>
      ) : (
        <div className="log">
          {log.map((e, i) => (
            <div className="log-row" key={i}>
              <span className="ts num">{e.ts}</span>
              <span className={`lvl ${e.lvl}`}>{e.lvl}</span>
              <span className="msg">{e.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
