import { useState } from 'react'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import type { ComponentState } from '../../../components/StatePill'
import '../engine.css'

export type ComponentAction = 'pause' | 'resume' | 'restart'

interface Props {
  name: string
  state: ComponentState
  onAction: (action: ComponentAction) => void
}

export function ActionBar({ name, state, onAction }: Props) {
  const [confirm, setConfirm] = useState<'pause' | 'restart' | null>(null)
  const isDisabled = state === 'disabled'

  return (
    <>
      <div className="comp-actions">
        {state === 'paused' ? (
          <button className="btn secondary" onClick={() => onAction('resume')}>
            Resume
          </button>
        ) : (
          <button className="btn secondary" disabled={isDisabled} onClick={() => setConfirm('pause')}>
            Pause
          </button>
        )}
        <button className="btn danger" disabled={isDisabled} onClick={() => setConfirm('restart')}>
          Force-restart
        </button>
      </div>

      {confirm === 'pause' && !isDisabled && (
        <ConfirmDialog
          open
          title="Pause component?"
          description={`Pauses ${name}. Backlog may grow while paused.`}
          confirmLabel="Pause"
          onConfirm={() => onAction('pause')}
          onOpenChange={(open) => {
            if (!open) setConfirm(null)
          }}
        />
      )}

      {confirm === 'restart' && !isDisabled && (
        <ConfirmDialog
          open
          variant="type-to-confirm"
          confirmWord={name}
          title="Force-restart component?"
          description={`Force-restarts ${name}. In-flight messages will be dropped.`}
          confirmLabel="Force-restart"
          danger
          onConfirm={() => onAction('restart')}
          onOpenChange={(open) => {
            if (!open) setConfirm(null)
          }}
        />
      )}
    </>
  )
}
