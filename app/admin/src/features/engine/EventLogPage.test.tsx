import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { EventLogPage } from './EventLogPage'
import { renderWithProviders } from '../../test/utils'

vi.mock('./useEvents', () => ({
  useEvents: () => ({
    data: [{ ts: 1749900000, lvl: 'ok', msg: 'processed INFY', api: 'corp_ann' }],
    isLoading: false,
    isError: false,
  }),
}))

describe('EventLogPage', () => {
  it('renders table headers and a datetime-formatted, levelled row', () => {
    renderWithProviders(<EventLogPage />)
    for (const header of ['Time', 'Component', 'Level', 'Message']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    expect(screen.getByText('processed INFY')).toBeInTheDocument()
    expect(screen.getByText('corp_ann')).toBeInTheDocument()
    expect(screen.getByText('OK')).toBeInTheDocument()
    // Time cell uses the "D Mon YYYY, h:mmAM/PM" format.
    expect(
      screen.getByText(/^\d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2}(AM|PM)$/),
    ).toBeInTheDocument()
  })
})
