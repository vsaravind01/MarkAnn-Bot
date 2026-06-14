import { render, screen, waitFor } from '@testing-library/react'
import { Outlet } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./features/auth/AuthGuard', () => ({
  AuthGuard: () => <Outlet />,
}))

vi.mock('./features/shell/ShellLayout', () => ({
  ShellLayout: () => <Outlet />,
}))

vi.mock('./features/engine/OverviewPage', () => ({
  OverviewPage: () => <div>Overview mock</div>,
}))

vi.mock('./features/engine/ProcessorsPage', () => ({
  ProcessorsPage: () => <div>Processors mock</div>,
}))

vi.mock('./features/engine/AlarmsPage', () => ({
  AlarmsPage: () => <div>Alarms mock</div>,
}))

vi.mock('./features/engine/EventLogPage', () => ({
  EventLogPage: () => <div>Events mock</div>,
}))

vi.mock('./features/engine/PollersPage', () => ({
  PollersPage: () => <div>Pollers mock</div>,
}))

vi.mock('./features/users/TradersPage', () => ({
  TradersPage: () => <div>Traders mock</div>,
}))

vi.mock('./features/users/AdminsPage', () => ({
  AdminsPage: () => <div>Admins mock</div>,
}))

describe('App routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
  })

  it('redirects /components to /overview', async () => {
    window.history.pushState({}, '', '/components')
    const { App } = await import('./App')
    render(<App />)
    await waitFor(() => expect(screen.getByText('Overview mock')).toBeInTheDocument())
  })

  it('redirects /engine/pools to /engine/processors', async () => {
    window.history.pushState({}, '', '/engine/pools')
    const { App } = await import('./App')
    render(<App />)
    await waitFor(() => expect(screen.getByText('Processors mock')).toBeInTheDocument())
  })
})
