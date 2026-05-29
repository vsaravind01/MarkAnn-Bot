import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { TradersPage } from './TradersPage'

vi.mock('../shell/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('./useTraders')
const { useTraders, useTraderPatch } = await import('./useTraders')

const mockTrader = {
  id: 1,
  email: 't@e.com',
  first_name: 'T',
  last_name: 'R',
  role: 'trader' as const,
  is_active: true,
  created_at: '2026-01-01T00:00:00',
}

describe('TradersPage', () => {
  it('renders trader rows', async () => {
    vi.mocked(useTraders).mockReturnValue({
      data: { items: [mockTrader], total: 1, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useTraders>)
    vi.mocked(useTraderPatch).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useTraderPatch>)

    renderWithProviders(<TradersPage />)

    await waitFor(() => expect(screen.getByText('t@e.com')).toBeInTheDocument())
    expect(screen.getByText('T R')).toBeInTheDocument()
  })

  it('shows disable button for active trader and confirm dialog on click', async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    vi.mocked(useTraders).mockReturnValue({
      data: { items: [mockTrader], total: 1, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useTraders>)
    vi.mocked(useTraderPatch).mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useTraderPatch>)

    renderWithProviders(<TradersPage />)

    await user.click(screen.getByRole('button', { name: /disable/i }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/disable this trader/i)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: /^disable$/i }))
    expect(mutate).toHaveBeenCalledWith(
      { id: mockTrader.id, is_active: false },
      expect.any(Object),
    )
  })
})
