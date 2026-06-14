import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricGrid } from './MetricGrid'

describe('MetricGrid', () => {
  it('renders each metric label and value', () => {
    render(<MetricGrid metrics={[{ label: 'Queue depth', value: '12' }, { label: 'Workers', value: '8' }]} />)
    expect(screen.getByText('Queue depth')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Workers')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
  })
})
