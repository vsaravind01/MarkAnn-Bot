import '../engine.css'

interface Props {
  value: number
  onChange: (next: number) => void
  label: string
  min?: number
  max?: number
  disabled?: boolean
}

export function Stepper({ value, onChange, label, min = 1, max = 64, disabled = false }: Props) {
  return (
    <div className="stepper">
      <button
        aria-label={`Decrease ${label}`}
        disabled={disabled || value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
      >
        -
      </button>
      <span className="val num">{value}</span>
      <button
        aria-label={`Increase ${label}`}
        disabled={disabled || value >= max}
        onClick={() => onChange(Math.min(max, value + 1))}
      >
        +
      </button>
    </div>
  )
}
