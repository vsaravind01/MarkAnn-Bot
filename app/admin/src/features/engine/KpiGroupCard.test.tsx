import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { KpiGroupCard } from './KpiGroupCard'

const items = [
  { id: 'a', name: 'a', subtitle: 'm', kind: 'poller' as const, state: 'running' as const, metrics: [] },
  { id: 'b', name: 'b', subtitle: 'm', kind: 'poller' as const, state: 'crit' as const, metrics: [] },
]

describe('KpiGroupCard', () => {
  it('summarizes running / total and alarm count', () => {
    render(<KpiGroupCard kind="poller" title="Pollers" items={items} />)
    expect(screen.getByText('Pollers')).toBeInTheDocument()
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
    expect(screen.getByText(/1 alarm/)).toBeInTheDocument()
  })
})
