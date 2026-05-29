import {
  Activity,
  Boxes,
  Gauge,
  type LucideIcon,
  Radio,
  Server,
  Settings,
  Shield,
  TriangleAlert,
  Users,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { usePollers } from '../engine/usePollers'

interface NavItemDef {
  to: string
  icon: LucideIcon
  label: string
  alarmCount?: number
}

export function Nav({ role }: { role: string }) {
  const { data: pollers = [] } = usePollers()
  const alarmCount = pollers.filter((p) => p.state === 'crit' || p.state === 'warn').length

  function item({ to, icon: Icon, label, alarmCount: count }: NavItemDef) {
    return (
      <NavLink key={to} to={to} className={({ isActive }) => `nav-item${isActive ? ' on' : ''}`}>
        <Icon size={15} />
        {label}
        {count != null && count > 0 && <span className="count alarm">{count}</span>}
      </NavLink>
    )
  }

  return (
    <nav className="nav">
      <div className="brand">
        <svg width="24" height="24" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="9" fill="#0F141D" />
          <rect x="0.5" y="0.5" width="39" height="39" rx="8.5" stroke="#fff" strokeOpacity=".10" />
          <g stroke="#4F7CFF" strokeWidth="2.6" strokeLinecap="round">
            <path d="M11 27.5V21.5" />
            <path d="M18 30V14" />
            <path d="M25 24V10" />
          </g>
          <path
            d="M11 22 L18 16 L25 12 L31 8"
            stroke="#4F7CFF"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="31" cy="8" r="2.6" fill="#4F7CFF" />
        </svg>
        <span className="word">
          Mark<span>Ann</span>
        </span>
        <span className="env">OPS</span>
      </div>

      {item({ to: '/overview', icon: Gauge, label: 'Overview' })}
      {item({ to: '/components', icon: Server, label: 'Components' })}
      {item({ to: '/alarms', icon: TriangleAlert, label: 'Alarms', alarmCount })}
      {item({ to: '/events', icon: Activity, label: 'Event log' })}

      <div className="sec-label">Engine</div>
      {item({ to: '/engine/pollers', icon: Radio, label: 'Pollers' })}
      {item({ to: '/engine/pools', icon: Boxes, label: 'Worker pools' })}

      {(role === 'admin' || role === 'superuser') && (
        <>
          <div className="sec-label">Users</div>
          {item({ to: '/users/traders', icon: Users, label: 'Traders' })}
          {role === 'superuser' && item({ to: '/users/admins', icon: Shield, label: 'Admins' })}
        </>
      )}

      <div className="spacer" />
      <button
        className="nav-item"
        style={{ background: 'none', border: 'none', cursor: 'default', opacity: 0.4 }}
      >
        <Settings size={15} />
        Settings
      </button>
    </nav>
  )
}
