import type { Metric } from '../types'
import '../engine.css'

export function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="metrics">
      {metrics.map((metric) => (
        <div className="metric" key={metric.label}>
          <div className="ml">{metric.label}</div>
          <div className={`mv num${metric.tone ? ` ${metric.tone}` : ''}`}>{metric.value}</div>
        </div>
      ))}
    </div>
  )
}
