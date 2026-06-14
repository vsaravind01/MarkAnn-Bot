import './components.css'

export type ComponentState = 'running' | 'paused' | 'warn' | 'crit' | 'disabled'

const META: Record<ComponentState, { cls: string; label: string }> = {
  running: { cls: 'state-ok live', label: 'Running' },
  paused: { cls: 'state-paused', label: 'Paused' },
  warn: { cls: 'state-warn', label: 'Degraded' },
  crit: { cls: 'state-crit', label: 'Tripped' },
  disabled: { cls: 'state-disabled', label: 'Disabled' },
}

export function StatePill({ state }: { state: ComponentState }) {
  const { cls, label } = META[state]
  return (
    <span className={`state-pill ${cls}`}>
      <span className="sd" />
      {label}
    </span>
  )
}
