import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ToastProvider } from '../shell/Toast'
import { ProcessorCard } from './ProcessorCard'

const resizeMutate = vi.fn()

vi.mock('./useProcessors', () => ({
  useProcessorAction: () => ({ mutate: vi.fn(), isPending: false }),
  useProcessorResize: () => ({ mutate: resizeMutate, isPending: false }),
}))

const processor = {
  id: 'corp_ann',
  name: 'corp_ann',
  subtitle: 'engine.processors.corp_ann',
  kind: 'processor' as const,
  state: 'running' as const,
  poolSize: 8,
  pollers: ['corp_ann'],
  metrics: [{ label: 'Workers', value: '8' }],
}

describe('ProcessorCard', () => {
  it('resizes the pool via the stepper', () => {
    renderWithProviders(
      <ToastProvider>
        <ProcessorCard processor={processor} />
      </ToastProvider>,
    )
    fireEvent.click(screen.getByLabelText('Increase pool size for corp_ann'))
    expect(resizeMutate).toHaveBeenCalledWith({ api: 'corp_ann', poolSize: 9 }, expect.anything())
  })
})
