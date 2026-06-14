import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ToastProvider } from '../shell/Toast'
import { ProcessorsPage } from './ProcessorsPage'

const processor = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.processors.corp_ann',
  kind: 'processor' as const,
  state: 'running' as const,
  poolSize: 8,
  pollers: ['corp_ann'],
  metrics: [
    { label: 'Queue depth', value: '3' },
    { label: 'Workers', value: '8' },
    { label: 'Pollers', value: 'corp_ann' },
  ],
}

const resizeMutate = vi.fn()

vi.mock('./useProcessors', () => ({
  useProcessors: () => ({ data: [processor], isLoading: false, isError: false }),
  useProcessorAction: () => ({ mutate: vi.fn(), isPending: false }),
  useProcessorResize: () => ({ mutate: resizeMutate, isPending: false }),
}))

describe('ProcessorsPage', () => {
  it('renders the processor row and resizes via the stepper', () => {
    renderWithProviders(
      <ToastProvider>
        <ProcessorsPage />
      </ToastProvider>,
    )
    expect(screen.getByText('engine.processors.corp_ann')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Increase workers for corp_ann'))
    expect(resizeMutate).toHaveBeenCalledWith({ api: 'corp_ann', poolSize: 9 }, expect.anything())
  })
})
