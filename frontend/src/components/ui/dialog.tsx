import { Modal } from '@heroui/react'
import clsx from 'clsx'
import type { ReactNode } from 'react'

/*
 * A dialog on HeroUI's Modal, under the names the code calls: an open state
 * from outside, a box with a close button, a heading and a line under it.
 */

type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  return (
    <Modal>
      <Modal.Backdrop isOpen={open} onOpenChange={onOpenChange}>
        {children}
      </Modal.Backdrop>
    </Modal>
  )
}

type ContentProps = {
  className?: string
  children: ReactNode
  /** The cross in the corner; a dialog with its own buttons for leaving can hide it. */
  showCloseButton?: boolean
}

export function DialogContent({ className, children, showCloseButton = true }: ContentProps) {
  return (
    <Modal.Container placement="center" scroll="inside">
      <Modal.Dialog
        className={clsx('max-h-[calc(100dvh-2rem)] gap-4 overflow-y-auto sm:max-w-lg', className)}
      >
        {showCloseButton && <Modal.CloseTrigger aria-label="Закрыть" />}
        {children}
      </Modal.Dialog>
    </Modal.Container>
  )
}

export function DialogHeader({ className, children }: { className?: string; children: ReactNode }) {
  return <Modal.Header className={clsx('gap-1.5 pr-8', className)}>{children}</Modal.Header>
}

export function DialogTitle({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <Modal.Heading className={clsx('text-lg font-semibold text-foreground', className)}>
      {children}
    </Modal.Heading>
  )
}

export function DialogDescription({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return <p className={clsx('text-sm text-muted', className)}>{children}</p>
}
