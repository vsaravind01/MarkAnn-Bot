import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { createTestQueryClient } from '../../test/utils'
import { LoginPage } from './LoginPage'

vi.mock('./useAuth')
vi.mock('../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api')>()
  return { ...actual, apiFetch: vi.fn() }
})

const { useAuth } = await import('./useAuth')
const { apiFetch } = await import('../../lib/api')

describe('LoginPage', () => {
  it('redirects to the original protected route after login', async () => {
    vi.mocked(useAuth).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAuth>)
    vi.mocked(apiFetch).mockResolvedValue({})

    const user = userEvent.setup()
    const client = createTestQueryClient()

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          initialEntries={[
            {
              pathname: '/login',
              state: { from: { pathname: '/engine/pollers', search: '?page=2', hash: '#row-3' } },
            },
          ]}
        >
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/engine/pollers" element={<div>Pollers destination</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await user.type(screen.getByLabelText(/email/i), 'ops@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(screen.getByText(/pollers destination/i)).toBeInTheDocument())
    expect(apiFetch).toHaveBeenCalledWith(
      '/auth/login',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
