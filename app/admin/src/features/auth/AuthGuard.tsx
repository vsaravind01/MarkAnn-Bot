import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

interface AuthGuardProps {
  requiredRole?: 'admin' | 'superuser'
}

const ROLE_ORDER: Record<string, number> = { trader: 0, admin: 1, superuser: 2 }

export function AuthGuard({ requiredRole }: AuthGuardProps) {
  const { data: user, isLoading, isError } = useAuth()
  const location = useLocation()

  if (isLoading) return <div className="loading-screen">Checking session…</div>
  if (isError || !user) return <Navigate to="/login" state={{ from: location }} replace />

  if (requiredRole && (ROLE_ORDER[user.role] ?? 0) < (ROLE_ORDER[requiredRole] ?? 0)) {
    return (
      <div className="forbidden-screen">
        <div>
          <h2 style={{ marginBottom: 8 }}>Access denied</h2>
          <p>You don't have permission to view this page.</p>
        </div>
      </div>
    )
  }

  return <Outlet />
}
