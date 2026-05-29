import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('simple variant: confirm button is always enabled', () => {
    render(
      <ConfirmDialog
        open
        title="Pause?"
        description="Pause it."
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /confirm/i })).not.toBeDisabled()
  })

  it('type-to-confirm: button disabled until correct word typed', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmDialog
        open
        variant="type-to-confirm"
        confirmWord="corp_ann"
        title="Restart?"
        description="This will restart."
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    )
    const btn = screen.getByRole('button', { name: /force-restart/i })
    expect(btn).toBeDisabled()
    await user.type(screen.getByRole('textbox'), 'corp_ann')
    expect(btn).not.toBeDisabled()
  })

  it('type-to-confirm: button stays disabled for wrong word', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmDialog
        open
        variant="type-to-confirm"
        confirmWord="corp_ann"
        title="Restart?"
        description="This will restart."
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    )
    await user.type(screen.getByRole('textbox'), 'wrong')
    expect(screen.getByRole('button', { name: /force-restart/i })).toBeDisabled()
  })

  it('uses a unique description id per dialog instance', () => {
    render(
      <>
        <ConfirmDialog
          open
          title="Pause?"
          description="Pause it."
          onConfirm={vi.fn()}
          onOpenChange={vi.fn()}
        />
        <ConfirmDialog
          open
          title="Restart?"
          description="Restart it."
          onConfirm={vi.fn()}
          onOpenChange={vi.fn()}
        />
      </>,
    )

    const ids = screen
      .getAllByRole('dialog', { hidden: true })
      .map((dialog) => dialog.getAttribute('aria-describedby'))
      .filter((value): value is string => Boolean(value))

    expect(new Set(ids).size).toBe(2)
  })
})
