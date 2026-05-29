import { useSearchParams } from 'react-router-dom'
import './components.css'

export function Pagination({ total, pageSize }: { total: number; pageSize: number }) {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1'))
  const totalPages = Math.ceil(total / pageSize)

  if (totalPages <= 1) return null

  function go(n: number) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('page', String(n))
      return next
    })
  }

  return (
    <div className="pagination">
      <button className="btn secondary" onClick={() => go(page - 1)} disabled={page <= 1}>
        Previous
      </button>
      <span className="pagination-info num">
        {page} / {totalPages}
      </span>
      <button className="btn secondary" onClick={() => go(page + 1)} disabled={page >= totalPages}>
        Next
      </button>
    </div>
  )
}
