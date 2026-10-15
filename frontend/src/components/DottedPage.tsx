import type { ReactNode } from 'react'
import { DottedVeil } from './ui/dotted-veil'

/**
 * A page outside the app's frame (the welcome and the introduction) on the same
 * page colour and breathing dots as the rest of the app.
 */
export function DottedPage({ children }: { children: ReactNode }) {
  return (
    <div className="isolate min-h-dvh bg-background">
      <DottedVeil className="dotted-veil" />
      {children}
    </div>
  )
}
