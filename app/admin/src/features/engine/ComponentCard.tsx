import { Bell, Boxes, Cpu, Radar, Radio, Server } from 'lucide-react'
import type { ElementType } from 'react'
import { useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { StatePill } from '../../components/StatePill'
import { useToast } from '../shell/Toast'
import './engine.css'
import type { PollerDisplay } from './types'
import { usePollerAction, type PollerAction } from './usePollers'
import { usePoolResize } from './usePools'

const ICONS: Record<string, ElementType> = {
  radio: Radio,
  server: Server,
  boxes: Boxes,
  cpu: Cpu,
  bell: Bell,
  radar: Radar,
}

const ACTION_META: Record<
  PollerAction,
  {
    title: string
    description: (name: string) => string
    confirm: string
    danger: boolean
    typeConfirm: boolean
  }
> = {
  restart: {
    title: 'Force-restart component?',
    description: (name) =>
      `Force-restarts ${name}. In-flight messages will be dropped and the component will reconnect from cold. This cannot be undone.`,
    confirm: 'Force-restart',
    danger: true,
    typeConfirm: true,
  },
  pause: {
    title: 'Pause component?',
    description: (name) =>
      `Pauses ${name}. It stops processing but holds its connections; resume any time. Backlog may grow while paused.`,
    confirm: 'Pause',
    danger: false,
    typeConfirm: false,
  },
  resume: {
    title: 'Resume component?',
    description: (name) => `Resumes ${name} and begins draining any backlog accrued while paused.`,
    confirm: 'Resume',
    danger: false,
    typeConfirm: false,
  },
}

interface Props {
  poller: PollerDisplay
  poolSize?: number
}

export function ComponentCard({ poller, poolSize }: Props) {
  const [confirmAction, setConfirmAction] = useState<PollerAction | null>(null)
  const pollerAction = usePollerAction()
  const poolResize = usePoolResize()
  const toast = useToast()

  const Icon = ICONS[poller.icon] ?? Server
  const cardCls = `comp${poller.state === 'crit' ? ' crit' : poller.state === 'warn' ? ' warn' : ''}`

  function handleActionConfirm() {
    if (!confirmAction) return
    pollerAction.mutate(
      { api: poller.id, action: confirmAction },
      {
        onSuccess: () =>
          toast.success(
            `${poller.name} ${
              confirmAction === 'restart' ? 'restarted' : confirmAction === 'pause' ? 'paused' : 'resumed'
            }`,
          ),
        onError: (err) => toast.error(err.message),
      },
    )
  }

  function handleResize(delta: number) {
    const current = poolSize ?? 1
    const next = Math.max(1, Math.min(64, current + delta))
    poolResize.mutate(
      { api: poller.id, size: next },
      {
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const meta = confirmAction ? ACTION_META[confirmAction] : null

  return (
    <>
      <div className={cardCls}>
        <div className="comp-top">
          <div className="comp-ico">
            <Icon size={16} />
          </div>
          <div>
            <div className="comp-name">{poller.name}</div>
            <div className="comp-type">{poller.type}</div>
          </div>
          <StatePill state={poller.state} />
        </div>

        <div className="metrics">
          {poller.metrics.map((m) => (
            <div className="metric" key={m.label}>
              <div className="ml">{m.label}</div>
              <div className={`mv num${m.tone ? ` ${m.tone}` : ''}`}>{m.value}</div>
            </div>
          ))}
        </div>

        {poolSize !== undefined && (
          <div className="pool">
            <span className="lab">Pool size</span>
            <div className="stepper">
              <button
                aria-label={`Decrease pool size for ${poller.name}`}
                disabled={poolResize.isPending}
                onClick={() => handleResize(-1)}
              >
                −
              </button>
              <span className="val num">{poolSize}</span>
              <button
                aria-label={`Increase pool size for ${poller.name}`}
                disabled={poolResize.isPending}
                onClick={() => handleResize(1)}
              >
                +
              </button>
            </div>
            <span className="lab" style={{ marginLeft: 'auto' }}>
              workers
            </span>
          </div>
        )}

        <div className="comp-actions">
          {poller.state === 'paused' ? (
            <button className="btn secondary" onClick={() => setConfirmAction('resume')}>
              Resume
            </button>
          ) : (
            <button className="btn secondary" onClick={() => setConfirmAction('pause')}>
              Pause
            </button>
          )}
          <button className="btn danger" onClick={() => setConfirmAction('restart')}>
            Force-restart
          </button>
        </div>
      </div>

      {meta &&
        (meta.typeConfirm ? (
          <ConfirmDialog
            open
            variant="type-to-confirm"
            confirmWord={poller.name}
            title={meta.title}
            description={meta.description(poller.name)}
            confirmLabel={meta.confirm}
            danger={meta.danger}
            onConfirm={handleActionConfirm}
            onOpenChange={(o) => {
              if (!o) setConfirmAction(null)
            }}
          />
        ) : (
          <ConfirmDialog
            open
            title={meta.title}
            description={meta.description(poller.name)}
            confirmLabel={meta.confirm}
            danger={meta.danger}
            onConfirm={handleActionConfirm}
            onOpenChange={(o) => {
              if (!o) setConfirmAction(null)
            }}
          />
        ))}
    </>
  )
}
