import { formatAgo } from './utils'
import { useEvents } from './useEvents'
import './engine.css'

const LVL_LABEL: Record<string, string> = {
  ok: 'OK',
  warn: 'WARN',
  crit: 'CRIT',
  info: 'INFO',
}

export function EventLogPage() {
  const { data: events = [], isLoading, isError } = useEvents()

  if (isLoading) return <div className="loading-screen">Loading…</div>
  if (isError) return <div className="empty-state">Unable to load the event log.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Event log</h2>
        <span className="page-sub">{events.length} entries</span>
      </div>
      {events.length === 0 ? (
        <div className="empty-state">No events yet — they appear as the engine runs.</div>
      ) : (
        <div className="log">
          {events.map((e, i) => (
            <div className="log-row" key={i}>
              <span className="ts num">{formatAgo(String(e.ts))}</span>
              <span className="log-api">{e.api ?? ''}</span>
              <span className={`lvl ${e.lvl}`}>{LVL_LABEL[e.lvl] ?? e.lvl}</span>
              <span className="msg">{e.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
