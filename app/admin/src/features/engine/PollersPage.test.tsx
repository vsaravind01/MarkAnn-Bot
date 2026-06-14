import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ToastProvider } from '../shell/Toast'
import { PollersPage } from './PollersPage'

const poller = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.pollers.corp_ann',
  kind: 'poller' as const,
  state: 'running' as const,
  metrics: [
    { label: 'Errors', value: '0' },
    { label: 'Interval', value: '5s' },
  ],
}

vi.mock('./usePollers', () => ({
  usePollers: () => ({ data: [poller], isLoading: false, isError: false }),
  usePollerAction: () => ({ mutate: vi.fn(), isPending: false }),
}))

describe('PollersPage', () => {
  it('renders the poller row with its module subtitle and metric columns', () => {
    renderWithProviders(
      <ToastProvider>
        <PollersPage />
      </ToastProvider>,
    )
    expect(screen.getByText('engine.pollers.corp_ann')).toBeInTheDocument()
    expect(screen.getByText('Interval')).toBeInTheDocument()
    expect(screen.getByText('5s')).toBeInTheDocument()
  })
})
