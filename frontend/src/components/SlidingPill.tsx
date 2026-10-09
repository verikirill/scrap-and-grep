import clsx from 'clsx'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

type Box = { x: number; y: number; width: number; height: number }

// Where a remembered pill last stood: a row rebuilt with its page (a profile's
// editor is, to drop unsaved edits) slides on from there instead of popping in.
const lastBoxes = new Map<string, { box: Box; at: number }>()
const REMEMBER_MS = 1500

const SLIDE = { type: 'spring', stiffness: 520, damping: 42 } as const
const STILL = { duration: 0 } as const

/**
 * The highlight of the chosen tab, sliding to the next choice. Its place is
 * read from the layout (offsetLeft and offsetTop), which page entrances do not
 * move: a highlight measured with getBoundingClientRect, as a shared layoutId
 * is, chased the page as it rose and flew in from above. It moves only when
 * the choice changes; a resize or a wrap puts it in place at once.
 *
 * The container is positioned and isolated; the chosen item carries
 * data-active="true".
 */
export function SlidingPill({
  container,
  activeKey,
  className,
  rememberAs,
}: {
  container: RefObject<HTMLElement | null>
  activeKey: string | null
  className?: string
  /** A name to carry the pill's place across a remount of its row. */
  rememberAs?: string
}) {
  const [from] = useState(() => {
    const last = rememberAs ? lastBoxes.get(rememberAs) : undefined
    return last && performance.now() - last.at < REMEMBER_MS ? last.box : null
  })
  const [box, setBox] = useState<Box | null>(null)
  const [isSliding, setSliding] = useState(from !== null)
  const [shownKey, setShownKey] = useState(activeKey)
  if (shownKey !== activeKey) {
    setShownKey(activeKey)
    setSliding(box !== null)
  }

  // An effect, not a layout effect: the container is the parent, and React
  // attaches a parent's ref after its children's layout effects have run.
  useEffect(() => {
    const root = container.current
    if (!root) return
    const measure = () => {
      const chosen = root.querySelector<HTMLElement>('[data-active="true"]')
      const next = chosen
        ? {
            x: chosen.offsetLeft,
            y: chosen.offsetTop,
            width: chosen.offsetWidth,
            height: chosen.offsetHeight,
          }
        : null
      if (next && rememberAs) lastBoxes.set(rememberAs, { box: next, at: performance.now() })
      setBox(next)
    }
    measure()
    // A ResizeObserver reports once as soon as it observes: that is not a
    // resize, and treating it as one stopped every slide.
    let isFirst = true
    const observer = new ResizeObserver(() => {
      if (isFirst) {
        isFirst = false
        return
      }
      setSliding(false)
      measure()
    })
    observer.observe(root)
    for (const child of root.children) observer.observe(child)
    return () => observer.disconnect()
  }, [container, activeKey, rememberAs])

  if (!box) return null
  return (
    <motion.span
      aria-hidden
      initial={from ?? false}
      animate={box}
      transition={isSliding ? SLIDE : STILL}
      className={clsx('pointer-events-none absolute top-0 left-0 -z-10', className)}
    />
  )
}
