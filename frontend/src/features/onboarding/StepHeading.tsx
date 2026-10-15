import { useContext, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { FocusStepContext } from './focus'

/** The title of a step, with a small line above it saying which part of the tour it is. */
export function StepHeading({ kicker, children }: { kicker?: ReactNode; children: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null)
  const shouldFocus = useContext(FocusStepContext)
  useEffect(() => {
    if (shouldFocus) ref.current?.focus({ preventScroll: true })
  }, [shouldFocus])

  return (
    <>
      {kicker && (
        <p className="mb-2 text-xs font-semibold tracking-wide text-accent uppercase">{kicker}</p>
      )}
      <h1
        ref={ref}
        tabIndex={-1}
        className="font-serif text-[28px] leading-tight font-semibold tracking-tight text-balance outline-none sm:text-[32px]"
      >
        {children}
      </h1>
    </>
  )
}
