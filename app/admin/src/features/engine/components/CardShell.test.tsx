import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CardShell } from './CardShell'

describe('CardShell', () => {
  it('renders name, subtitle, state label, and children', () => {
    render(
      <CardShell kind="processor" name="corp_ann" subtitle="engine.processors.corp_ann" state="running">
        <div>body</div>
      </CardShell>,
    )
    expect(screen.getByText('corp_ann')).toBeInTheDocument()
    expect(screen.getByText('engine.processors.corp_ann')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('body')).toBeInTheDocument()
  })
})
