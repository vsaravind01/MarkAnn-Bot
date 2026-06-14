import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ToastProvider } from '../shell/Toast'
import { OverviewPage } from './OverviewPage'

const poller = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.pollers.corp_ann',
  kind: 'poller' as const,
  state: 'running' as const,
  metrics: [],
}

const processor = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.processors.corp_ann',
  kind: 'processor' as const,
  state: 'running' as const,
  poolSize: 8,
  pollers: ['corp_ann'],
  metrics: [],
}

vi.mock('./usePollers', () => ({
  usePollers: () => ({ data: [poller], isLoading: false, isError: false }),
  usePollerAction: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('./useProcessors', () => ({
  useProcessors: () => ({ data: [processor], isLoading: false, isError: false }),
  useProcessorAction: () => ({ mutate: vi.fn(), isPending: false }),
  useProcessorResize: () => ({ mutate: vi.fn(), isPending: false }),
}))

describe('OverviewPage', () => {
  it('shows per-kind KPI cards and a split health section', () => {
    renderWithProviders(
      <ToastProvider>
        <OverviewPage />
      </ToastProvider>,
    )
    expect(screen.getAllByText('Pollers')).not.toHaveLength(0)
    expect(screen.getAllByText('Processors')).not.toHaveLength(0)
    expect(screen.getByText('engine.pollers.corp_ann')).toBeInTheDocument()
    expect(screen.getByText('engine.processors.corp_ann')).toBeInTheDocument()
  })
})
