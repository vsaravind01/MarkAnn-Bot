import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthGuard } from './features/auth/AuthGuard'
import { BootstrapPage } from './features/auth/BootstrapPage'
import { LoginPage } from './features/auth/LoginPage'
import { ShellLayout } from './features/shell/ShellLayout'
import { ToastProvider } from './features/shell/Toast'

const OverviewPage = lazy(() =>
  import('./features/engine/OverviewPage').then((m) => ({ default: m.OverviewPage })),
)
const ComponentsPage = lazy(() =>
  import('./features/engine/ComponentsPage').then((m) => ({ default: m.ComponentsPage })),
)
const AlarmsPage = lazy(() =>
  import('./features/engine/AlarmsPage').then((m) => ({ default: m.AlarmsPage })),
)
const EventLogPage = lazy(() =>
  import('./features/engine/EventLogPage').then((m) => ({ default: m.EventLogPage })),
)
const PollersPage = lazy(() =>
  import('./features/engine/PollersPage').then((m) => ({ default: m.PollersPage })),
)
const PoolsPage = lazy(() =>
  import('./features/engine/PoolsPage').then((m) => ({ default: m.PoolsPage })),
)
const TradersPage = lazy(() =>
  import('./features/users/TradersPage').then((m) => ({ default: m.TradersPage })),
)
const AdminsPage = lazy(() =>
  import('./features/users/AdminsPage').then((m) => ({ default: m.AdminsPage })),
)

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Suspense fallback={<div className="loading-screen">Loading…</div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/bootstrap" element={<BootstrapPage />} />
            <Route element={<AuthGuard />}>
              <Route element={<ShellLayout />}>
                <Route index element={<Navigate to="/overview" replace />} />
                <Route path="overview" element={<OverviewPage />} />
                <Route path="components" element={<ComponentsPage />} />
                <Route path="alarms" element={<AlarmsPage />} />
                <Route path="events" element={<EventLogPage />} />
                <Route path="engine/pollers" element={<PollersPage />} />
                <Route path="engine/pools" element={<PoolsPage />} />
                <Route element={<AuthGuard requiredRole="admin" />}>
                  <Route path="users/traders" element={<TradersPage />} />
                </Route>
                <Route element={<AuthGuard requiredRole="superuser" />}>
                  <Route path="users/admins" element={<AdminsPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Routes>
        </Suspense>
      </ToastProvider>
    </BrowserRouter>
  )
}
