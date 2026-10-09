import { Popover as HeroPopover } from '@heroui/react'
import clsx from 'clsx'
import { Pressable } from 'react-aria-components'
import type { DOMAttributes, ReactElement, ReactNode } from 'react'

type Pressed = ReactElement<DOMAttributes<Element>, string>

/*
 * A popover on HeroUI's, under the names the code calls: an open state held
 * outside, a trigger the reader presses and a box aligned to it.
 */

type PopoverProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}

export function Popover({ open, onOpenChange, children }: PopoverProps) {
  return (
    <HeroPopover isOpen={open} onOpenChange={onOpenChange}>
      {children}
    </HeroPopover>
  )
}

/** The button that opens the popover; the popover lines up with it. */
export function PopoverTrigger({ children }: { children: ReactElement; asChild?: boolean }) {
  return <Pressable>{children as Pressed}</Pressable>
}

type ContentProps = {
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'bottom'
  /** Distance kept from the window's edges, in pixels. */
  collisionPadding?: number
  className?: string
  children: ReactNode
}

export function PopoverContent({
  align = 'center',
  side = 'bottom',
  collisionPadding = 12,
  className,
  children,
}: ContentProps) {
  const placement = align === 'center' ? side : (`${side} ${align}` as const)
  return (
    <HeroPopover.Content placement={placement} offset={8} containerPadding={collisionPadding}>
      <HeroPopover.Dialog className={clsx('outline-none', className)}>
        {children}
      </HeroPopover.Dialog>
    </HeroPopover.Content>
  )
}
