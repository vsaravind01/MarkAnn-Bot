import { formatDateTime } from './utils'
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
        <table className="engine-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Component</th>
              <th>Level</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event, i) => (
              <tr key={i}>
                <td className="num">{formatDateTime(event.ts)}</td>
                <td className="log-api">{event.api ?? '—'}</td>
                <td>
                  <span className={`lvl ${event.lvl}`}>{LVL_LABEL[event.lvl] ?? event.lvl}</span>
                </td>
                <td className="msg">{event.msg}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
