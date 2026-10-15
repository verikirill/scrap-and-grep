import type { ReactNode } from 'react'
import { cn } from '../lib/utils'

/**
 * A soft light tile under a picture of the black cat, as under the logo: on a
 * dark surface the cat would vanish otherwise. The same in both themes.
 */
export function ArtTile({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'grid max-w-full place-items-center rounded-[2rem] bg-white p-4 shadow-surface ring-1 ring-black/5',
        className,
      )}
    >
      {children}
    </div>
  )
}
