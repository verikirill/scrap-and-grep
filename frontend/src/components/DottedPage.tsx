import { useLayoutEffect } from 'react'
import type { ReactNode } from 'react'
import { prefersDark } from '../lib/theme'
import { DottedVeil } from './ui/dotted-veil'

/**
 * A page outside the app's frame (the welcome and the introduction) on the same
 * page colour and breathing dots as the rest of the app. Opened straight from
 * the address bar, as right after registration, it takes the reader's theme
 * itself: the switch lives in the app's frame.
 */
export function DottedPage({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    document.documentElement.classList.toggle('dark', prefersDark())
  }, [])

  return (
    <div className="isolate min-h-dvh bg-background">
      <DottedVeil className="dotted-veil" />
      {children}
    </div>
  )
}
