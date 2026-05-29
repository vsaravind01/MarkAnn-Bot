import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { AuthGuard } from './AuthGuard'

vi.mock('./useAuth')
const { useAuth } = await import('./useAuth')

describe('AuthGuard', () => {
  function renderGuard(requiredRole?: 'admin' | 'superuser', initialEntries?: string[]) {
    return renderWithProviders(
      <Routes>
        <Route element={<AuthGuard requiredRole={requiredRole} />}>
          <Route path="/overview" element={<div>Protected page</div>} />
        </Route>
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>,
      { initialEntries: initialEntries ?? ['/overview'] },
    )
  }

  it('shows loading while fetching', () => {
    vi.mocked(useAuth).mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    } as ReturnType<typeof useAuth>)
    renderGuard()
    expect(screen.getByText(/checking session/i)).toBeInTheDocument()
  })

  it('redirects to /login when not authenticated', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    } as ReturnType<typeof useAuth>)
    renderGuard()
    await waitFor(() => expect(screen.getByText(/login page/i)).toBeInTheDocument())
  })

  it('shows forbidden screen for insufficient role', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isLoading: false,
      isError: false,
      data: { id: 1, email: 'a@b.com', role: 'admin', first_name: 'A', last_name: 'B', is_active: true },
    } as ReturnType<typeof useAuth>)
    renderGuard('superuser')
    await waitFor(() => expect(screen.getByText(/access denied/i)).toBeInTheDocument())
  })
})
