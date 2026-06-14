import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatePill } from './StatePill'

describe('StatePill', () => {
  it('renders the disabled state label', () => {
    render(<StatePill state="disabled" />)
    expect(screen.getByText('Disabled')).toBeInTheDocument()
  })
})
