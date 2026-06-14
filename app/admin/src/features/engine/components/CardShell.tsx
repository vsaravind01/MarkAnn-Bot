import { Cpu, Radio } from 'lucide-react'
import type { ReactNode } from 'react'
import { StatePill, type ComponentState } from '../../../components/StatePill'
import type { ComponentKind } from '../types'
import '../engine.css'

const KIND_ICON = {
  poller: Radio,
  processor: Cpu,
} as const

interface Props {
  kind: ComponentKind
  name: string
  subtitle: string
  state: ComponentState
  children: ReactNode
}

export function CardShell({ kind, name, subtitle, state, children }: Props) {
  const Icon = KIND_ICON[kind]
  const tone =
    state === 'crit' ? ' crit' : state === 'warn' ? ' warn' : state === 'disabled' ? ' disabled' : ''

  return (
    <div className={`comp${tone}`}>
      <div className="comp-top">
        <div className="comp-ico">
          <Icon size={16} />
        </div>
        <div>
          <div className="comp-name">{name}</div>
          <div className="comp-type">{subtitle}</div>
        </div>
        <StatePill state={state} />
      </div>
      {children}
    </div>
  )
}
