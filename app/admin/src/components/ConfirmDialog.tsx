import * as Dialog from '@radix-ui/react-dialog'
import { RotateCcw, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'
import './components.css'

interface BaseProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm: () => void
  confirmLabel?: string
  danger?: boolean
}

interface SimpleProps extends BaseProps {
  variant?: 'simple'
}

interface TypeConfirmProps extends BaseProps {
  variant: 'type-to-confirm'
  confirmWord: string
}

type ConfirmDialogProps = SimpleProps | TypeConfirmProps

export function ConfirmDialog(props: ConfirmDialogProps) {
  const { open, onOpenChange, title, description, onConfirm, danger = false } = props
  const descriptionId = useId()
  const isTypeConfirm = props.variant === 'type-to-confirm'
  const confirmWord = isTypeConfirm ? (props as TypeConfirmProps).confirmWord : ''
  const confirmLabel = props.confirmLabel ?? (isTypeConfirm ? 'Force-restart' : 'Confirm')
  const [typed, setTyped] = useState('')
  const canConfirm = !isTypeConfirm || typed === confirmWord

  function handleConfirm() {
    if (!canConfirm) return
    onConfirm()
    onOpenChange(false)
    setTyped('')
  }

  function handleOpenChange(next: boolean) {
    if (!next) setTyped('')
    onOpenChange(next)
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="scrim" />
        <Dialog.Content className="modal" aria-describedby={descriptionId}>
          <div className="modal-head">
            <div
              className="warn-ico"
              style={danger ? {} : { background: 'var(--accent-soft)', color: 'var(--accent)' }}
            >
              {danger ? <TriangleAlert size={17} /> : <RotateCcw size={17} />}
            </div>
            <Dialog.Title className="modal-title">{title}</Dialog.Title>
          </div>
          <div className="modal-body" id={descriptionId}>
            <Dialog.Description asChild>
              <p>{description}</p>
            </Dialog.Description>
            {isTypeConfirm && (
              <div className="confirm-field">
                <label>
                  Type <span className="target">{confirmWord}</span> to confirm
                </label>
                <input
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={confirmWord}
                  autoFocus
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
            )}
          </div>
          <div className="modal-foot">
            <button className="btn ghost" onClick={() => handleOpenChange(false)}>
              Cancel
            </button>
            <button className={`btn ${danger ? 'danger' : 'primary'}`} onClick={handleConfirm} disabled={!canConfirm}>
              {confirmLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
