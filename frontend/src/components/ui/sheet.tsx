import { Drawer } from '@heroui/react'
import clsx from 'clsx'
import { Pressable } from 'react-aria-components'
import type { DOMAttributes, ReactElement, ReactNode } from 'react'

type Pressed = ReactElement<DOMAttributes<Element>, string>

/*
 * A side or bottom sheet on HeroUI's Drawer, under the names the code calls.
 * It opens from its trigger, or from an open state held outside.
 */

type SheetProps = {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: ReactNode
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  return (
    <Drawer isOpen={open} onOpenChange={onOpenChange}>
      {children}
    </Drawer>
  )
}

/** Opens the sheet: the child is the button the reader presses. */
export function SheetTrigger({ children }: { children: ReactElement; asChild?: boolean }) {
  return <Pressable>{children as Pressed}</Pressable>
}

type ContentProps = {
  side?: 'top' | 'right' | 'bottom' | 'left'
  className?: string
  children: ReactNode
}

export function SheetContent({ side = 'right', className, children }: ContentProps) {
  return (
    <Drawer.Backdrop>
      <Drawer.Content placement={side}>
        <Drawer.Dialog className={clsx('gap-4 overflow-y-auto', className)}>
          {side === 'bottom' && <Drawer.Handle />}
          <Drawer.CloseTrigger aria-label="Закрыть" />
          {children}
        </Drawer.Dialog>
      </Drawer.Content>
    </Drawer.Backdrop>
  )
}

export function SheetHeader({ className, children }: { className?: string; children: ReactNode }) {
  return <Drawer.Header className={clsx('gap-1 pr-8', className)}>{children}</Drawer.Header>
}

export function SheetTitle({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <Drawer.Heading className={clsx('text-lg font-semibold text-foreground', className)}>
      {children}
    </Drawer.Heading>
  )
}

export function SheetDescription({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return <p className={clsx('text-sm text-muted', className)}>{children}</p>
}
