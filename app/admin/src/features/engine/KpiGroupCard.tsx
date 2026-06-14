import { Cpu, Radio } from 'lucide-react'
import type { ComponentDisplay, ComponentKind } from './types'
import './engine.css'

const KIND_ICON = { poller: Radio, processor: Cpu } as const

interface Props {
  kind: ComponentKind
  title: string
  items: ComponentDisplay[]
}

export function KpiGroupCard({ kind, title, items }: Props) {
  const Icon = KIND_ICON[kind]
  const total = items.length
  const running = items.filter((item) => item.state === 'running').length
  const paused = items.filter((item) => item.state === 'paused').length
  const alarms = items.filter((item) => item.state === 'crit').length
  const disabled = items.filter((item) => item.state === 'disabled').length

  return (
    <div className={`kpi-group${alarms > 0 ? ' crit' : ''}`}>
      <div className="kpi-group-head">
        <Icon size={14} />
        <span className="kpi-group-title">{title}</span>
        <span className="kpi-group-count num">{total} registered</span>
      </div>
      <div className="kpi-group-headline">
        <span className="num">
          {running} / {total}
        </span>
        <span className="kpi-group-sub">running</span>
      </div>
      <div className="kpi-group-chips">
        <span className="chip">{running} running</span>
        <span className="chip">{paused} paused</span>
        <span className={`chip${alarms > 0 ? ' crit' : ''}`}>
          {alarms} alarm{alarms === 1 ? '' : 's'}
        </span>
        <span className="chip">{disabled} disabled</span>
      </div>
    </div>
  )
}
