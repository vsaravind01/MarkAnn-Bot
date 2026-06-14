import { KpiGroupCard } from './KpiGroupCard'
import { PollerCard } from './PollerCard'
import { ProcessorCard } from './ProcessorCard'
import './engine.css'
import { usePollers } from './usePollers'
import { useProcessors } from './useProcessors'

export function OverviewPage() {
  const { data: pollers = [], isLoading: pollersLoading, isError: pollersError } = usePollers()
  const {
    data: processors = [],
    isLoading: processorsLoading,
    isError: processorsError,
  } = useProcessors()

  if (pollersLoading || processorsLoading) {
    return <div className="loading-screen">Loading engine health…</div>
  }
  if (pollersError || processorsError) {
    return <div className="empty-state">Unable to load engine health right now.</div>
  }

  return (
    <div>
      <div className="page-head">
        <h2>Overview</h2>
      </div>

      <div className="kpi-row">
        <KpiGroupCard kind="poller" title="Pollers" items={pollers} />
        <KpiGroupCard kind="processor" title="Processors" items={processors} />
      </div>

      <div className="sec-label-main">Component health</div>
      <div className="health-split">
        <section>
          <div className="health-col-head">Pollers</div>
          {pollers.length === 0 ? (
            <div className="empty-state">No pollers registered.</div>
          ) : (
            <div className="grid">
              {pollers.map((poller) => (
                <PollerCard key={poller.id} poller={poller} />
              ))}
            </div>
          )}
        </section>
        <section>
          <div className="health-col-head">Processors</div>
          {processors.length === 0 ? (
            <div className="empty-state">No processors registered.</div>
          ) : (
            <div className="grid">
              {processors.map((processor) => (
                <ProcessorCard key={processor.id} processor={processor} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
