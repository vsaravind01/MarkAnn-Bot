import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ActionBar } from './ActionBar'

describe('ActionBar', () => {
  it('fires resume immediately when paused', () => {
    const onAction = vi.fn()
    render(<ActionBar name="corp_ann" state="paused" onAction={onAction} />)
    fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
    expect(onAction).toHaveBeenCalledWith('resume')
  })

  it('confirms before pausing', () => {
    const onAction = vi.fn()
    render(<ActionBar name="corp_ann" state="running" onAction={onAction} />)
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(onAction).not.toHaveBeenCalled()
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Pause' }))
    expect(onAction).toHaveBeenCalledWith('pause')
  })

  it('disables mutating actions when the component is disabled', () => {
    const onAction = vi.fn()
    render(<ActionBar name="corp_ann" state="disabled" onAction={onAction} />)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Force-restart' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(onAction).not.toHaveBeenCalled()
  })
})
