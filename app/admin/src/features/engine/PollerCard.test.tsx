import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ToastProvider } from '../shell/Toast'
import { PollerCard } from './PollerCard'

vi.mock('./usePollers', () => ({
  usePollerAction: () => ({ mutate: vi.fn(), isPending: false }),
}))

const poller = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.pollers.corp_ann',
  kind: 'poller' as const,
  state: 'running' as const,
  metrics: [{ label: 'Errors', value: '0' }],
}

describe('PollerCard', () => {
  it('renders name, subtitle, and a pause action', () => {
    renderWithProviders(
      <ToastProvider>
        <PollerCard poller={poller} />
      </ToastProvider>,
    )
    expect(screen.getByText('corp_ann')).toBeInTheDocument()
    expect(screen.getByText('engine.pollers.corp_ann')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })
})
