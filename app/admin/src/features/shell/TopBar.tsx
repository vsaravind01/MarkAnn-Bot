import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import type { AuthUser } from '../auth/types'
import { usePollers } from '../engine/usePollers'

function GlobalStatePill({ pollers }: { pollers: Array<{ state: string }> }) {
  const hasCrit = pollers.some((p) => p.state === 'crit')
  const hasWarn = pollers.some((p) => p.state === 'warn')
  const cls = hasCrit ? 'crit' : hasWarn ? 'warn' : 'ok'
  const label = hasCrit ? 'Alarm active' : hasWarn ? 'Attention needed' : 'All systems nominal'
  return (
    <div className={`global-state ${cls}`}>
      <span className="dot" />
      {label}
    </div>
  )
}

export function TopBar({ user }: { user: AuthUser }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: pollers = [] } = usePollers()

  const logout = useMutation({
    mutationFn: () => apiFetch('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })

  return (
    <header className="topbar">
      <h1>Operations</h1>
      <GlobalStatePill pollers={pollers} />
      <div className="spacer" />
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className="btn ghost" style={{ gap: 8 }}>
            {user.first_name} {user.last_name}
            <span className="role-badge">{user.role}</span>
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="dropdown-content" align="end" sideOffset={6}>
            <DropdownMenu.Item className="dropdown-item danger" onSelect={() => logout.mutate()}>
              <LogOut size={13} />
              Log out
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  )
}
