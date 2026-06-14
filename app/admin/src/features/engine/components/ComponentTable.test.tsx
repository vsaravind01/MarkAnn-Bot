import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ComponentTable, type Column } from './ComponentTable'

interface Row {
  id: string
  name: string
}

const columns: Column<Row>[] = [{ key: 'name', header: 'Name', render: (r) => r.name }]

describe('ComponentTable', () => {
  it('renders headers and rows', () => {
    render(<ComponentTable columns={columns} rows={[{ id: '1', name: 'corp_ann' }]} rowKey={(r) => r.id} empty="none" />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('corp_ann')).toBeInTheDocument()
  })

  it('renders the empty state when no rows', () => {
    render(<ComponentTable columns={columns} rows={[]} rowKey={(r) => r.id} empty="No rows here" />)
    expect(screen.getByText('No rows here')).toBeInTheDocument()
  })
})
