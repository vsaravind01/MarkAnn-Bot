import { Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Nav } from './Nav'
import { TopBar } from './TopBar'
import './shell.css'

export function ShellLayout() {
  const { data: user } = useAuth()
  if (!user) return null

  return (
    <div className="app-shell">
      <TopBar user={user} />
      <Nav role={user.role} />
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
