import { Activity, Bell, Cpu, Gauge } from 'lucide-react'
import type { ElementType } from 'react'
import { ComponentCard } from './ComponentCard'
import './engine.css'
import { usePollers } from './usePollers'
import { usePools } from './usePools'

function KpiCard({
  icon: Icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: ElementType
  label: string
  value: string
  detail: string
  tone?: 'warn' | 'crit'
}) {
  const color = tone === 'crit' ? 'var(--crit)' : tone === 'warn' ? 'var(--warn)' : 'var(--fg-1)'
  return (
    <div className="kpi">
      <div className="l eyebrow">
        <Icon size={12} />
        {label}
      </div>
      <div className="v num" style={{ color }}>
        {value}
      </div>
      <div className="d num">{detail}</div>
    </div>
  )
}

export function OverviewPage() {
  const { data: pollers = [], isLoading, isError } = usePollers()
  const apis = pollers.map((p) => p.id)
  const { poolSizes, isError: poolsError } = usePools(apis)

  const total = pollers.length
  const alarms = pollers.filter((p) => p.state === 'crit').length
  const degraded = pollers.filter((p) => p.state === 'warn').length
  const healthTone = alarms > 0 ? 'crit' : degraded > 0 ? 'warn' : undefined

  if (isLoading) return <div className="loading-screen">Loading engine health…</div>
  if (isError || poolsError) return <div className="empty-state">Unable to load engine health right now.</div>

  return (
    <div>
      <div className="page-head">
        <h2>Overview</h2>
      </div>

      <div className="kpi-row">
        <KpiCard
          icon={Gauge}
          label="System health"
          value={`${total - alarms - degraded} / ${total}`}
          detail={alarms > 0 ? `${alarms} in alarm` : degraded > 0 ? `${degraded} degraded` : 'All nominal'}
          tone={healthTone}
        />
        <KpiCard
          icon={Activity}
          label="Active alarms"
          value={String(alarms)}
          detail={alarms === 0 ? 'None' : 'Requires attention'}
          tone={alarms > 0 ? 'crit' : undefined}
        />
        <KpiCard icon={Cpu} label="Components" value={String(total)} detail="Registered" />
        <KpiCard
          icon={Bell}
          label="Degraded"
          value={String(degraded)}
          detail={degraded === 0 ? 'None' : 'Watch queue'}
          tone={degraded > 0 ? 'warn' : undefined}
        />
      </div>

      <div className="sec-label-main">Component health</div>
      {pollers.length === 0 ? (
        <div className="empty-state">No components registered. Start the engine to see health data.</div>
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
