import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Stepper } from './Stepper'

describe('Stepper', () => {
  it('increments and decrements within bounds', () => {
    const onChange = vi.fn()
    render(<Stepper value={2} onChange={onChange} label="pool size" />)
    fireEvent.click(screen.getByLabelText('Increase pool size'))
    fireEvent.click(screen.getByLabelText('Decrease pool size'))
    expect(onChange).toHaveBeenNthCalledWith(1, 3)
    expect(onChange).toHaveBeenNthCalledWith(2, 1)
  })

  it('disables decrement at min and increment at max', () => {
    const onChange = vi.fn()
    const { rerender } = render(<Stepper value={1} min={1} max={3} onChange={onChange} label="x" />)
    expect(screen.getByLabelText('Decrease x')).toBeDisabled()
    rerender(<Stepper value={3} min={1} max={3} onChange={onChange} label="x" />)
    expect(screen.getByLabelText('Increase x')).toBeDisabled()
  })
})
