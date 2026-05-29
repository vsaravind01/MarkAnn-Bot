import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { AdminsPage } from './AdminsPage'

vi.mock('../shell/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('./useAdmins')
const { useAdmins, useAdminPatch, useAdminCreate } = await import('./useAdmins')

const mockSuperuser = {
  id: 1,
  email: 'super@e.com',
  first_name: 'Super',
  last_name: 'User',
  role: 'superuser' as const,
  is_active: true,
  created_at: '2026-01-01T00:00:00',
}

const mockAdmin = {
  id: 2,
  email: 'admin@e.com',
  first_name: 'Admin',
  last_name: 'User',
  role: 'admin' as const,
  is_active: true,
  created_at: '2026-01-02T00:00:00',
}

describe('AdminsPage', () => {
  beforeEach(() => {
    vi.mocked(useAdminPatch).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useAdminPatch>)
    vi.mocked(useAdminCreate).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useAdminCreate>)
  })

  it('renders admin rows', async () => {
    vi.mocked(useAdmins).mockReturnValue({
      data: { items: [mockSuperuser, mockAdmin], total: 2, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useAdmins>)

    renderWithProviders(<AdminsPage />)

    await waitFor(() => expect(screen.getByText('super@e.com')).toBeInTheDocument())
    expect(screen.getByText('admin@e.com')).toBeInTheDocument()
  })

  it('disable button is absent for superuser row', async () => {
    vi.mocked(useAdmins).mockReturnValue({
      data: { items: [mockSuperuser], total: 1, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useAdmins>)

    renderWithProviders(<AdminsPage />)

    await waitFor(() => expect(screen.getByText('super@e.com')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /disable/i })).not.toBeInTheDocument()
  })

  it('opens create admin dialog on button click', async () => {
    const user = userEvent.setup()
    vi.mocked(useAdmins).mockReturnValue({
      data: { items: [] as Array<typeof mockAdmin>, total: 0, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useAdmins>)

    renderWithProviders(<AdminsPage />)

    await user.click(screen.getByRole('button', { name: /create admin/i }))
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  })

  it('confirms disable for a non-superuser admin', async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    vi.mocked(useAdminPatch).mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useAdminPatch>)
    vi.mocked(useAdmins).mockReturnValue({
      data: { items: [mockAdmin], total: 1, page: 1, page_size: 20 },
      isLoading: false,
    } as ReturnType<typeof useAdmins>)

    renderWithProviders(<AdminsPage />)

    await user.click(screen.getByRole('button', { name: /disable/i }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/disable this admin/i)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: /^disable$/i }))
    expect(mutate).toHaveBeenCalledWith(
      { id: mockAdmin.id, is_active: false },
      expect.any(Object),
    )
  })
})
