import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'motion/react'
import { useLayoutEffect, useRef } from 'react'
import type { RefObject } from 'react'
import { cn } from '../lib/utils'

type Axis = 'x' | 'y'

// The edge nearer the new place runs ahead, the far one follows softer: on
// the way the indicator stretches like a drop rolling over, and it draws
// itself together with a small bounce when it arrives.
const LEAD = { type: 'spring', stiffness: 420, damping: 28, mass: 0.8 } as const
const TRAIL = { type: 'spring', stiffness: 190, damping: 21, mass: 1 } as const
// How much thinner the drop gets as it stretches, at most.
const MAX_SQUEEZE = 0.34
const SQUEEZE_PER_STRETCH = 0.2

type Props = {
  /** The positioned element the indicator lives in. */
  container: RefObject<HTMLElement | null>
  /** Changes when the chosen item does; the indicator moves then. */
  targetKey: string | null
  /** The element the indicator settles on, read after the render. */
  getTarget: () => HTMLElement | null | undefined
  axis: Axis
  className?: string
}

/** The highlight behind a chosen item that flows to the next one like a drop. */
export function LiquidIndicator({ container, targetKey, getTarget, axis, className }: Props) {
  const isStill = useReducedMotion()
  const start = useMotionValue(0)
  const end = useMotionValue(0)
  const crossStart = useMotionValue(0)
  const crossSize = useMotionValue(0)
  const opacity = useMotionValue(0)
  const restLength = useRef(1)
  const isPlaced = useRef(false)
  const length = useTransform(() => end.get() - start.get())
  const squeeze = useTransform(() => {
    const stretch = Math.max(0, length.get() / restLength.current - 1)
    return 1 - Math.min(MAX_SQUEEZE, stretch * SQUEEZE_PER_STRETCH)
  })

  useLayoutEffect(() => {
    const box = container.current
    const found = getTarget()
    if (!box || !found) {
      // On the first render neither the container (a parent, whose ref React
      // attaches after its children's effects) nor the items may be there
      // yet: look again on the next frame, reading both anew.
      opacity.set(0)
      let stop: (() => void) | undefined
      const retry = requestAnimationFrame(() => {
        const lateBox = container.current
        const late = getTarget()
        if (lateBox && late) stop = placeOn(lateBox, late)
      })
      return () => {
        cancelAnimationFrame(retry)
        stop?.()
      }
    }
    return placeOn(box, found)

    function placeOn(box: HTMLElement, target: HTMLElement): () => void {
      const place = (isMove: boolean) => {
        const outer = box.getBoundingClientRect()
        const inner = target.getBoundingClientRect()
        // An absolute child is placed from the padding box, which starts
        // inside the border and moves with the scroll.
        const left = inner.left - outer.left - box.clientLeft + box.scrollLeft
        const top = inner.top - outer.top - box.clientTop + box.scrollTop
        const [from, size, across, thickness] =
          axis === 'y'
            ? [top, inner.height, left, inner.width]
            : [left, inner.width, top, inner.height]
        restLength.current = size || 1
        crossStart.set(across)
        crossSize.set(thickness)
        opacity.set(1)
        if (!isMove || !isPlaced.current || isStill) {
          // A resize mid-move wins over the springs still running to the old spot.
          start.jump(from)
          end.jump(from + size)
          isPlaced.current = true
          return
        }
        const isForward = from > start.get()
        animate(isForward ? end : start, isForward ? from + size : from, LEAD)
        animate(isForward ? start : end, isForward ? from : from + size, TRAIL)
      }
      place(true)
      // A resize moves things without a choice: the indicator follows at once.
      // The observer reports once on start; that report is the one just made.
      let isFirst = true
      const observer = new ResizeObserver(() => {
        if (isFirst) {
          isFirst = false
          return
        }
        place(false)
      })
      observer.observe(box)
      // The item may move without the container changing size: a label
      // wrapping, a font arriving.
      observer.observe(target)
      return () => observer.disconnect()
    }
    // getTarget is read when the key changes; a new function each render is not a move.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey, axis, isStill])

  const style =
    axis === 'y'
      ? { top: start, height: length, left: crossStart, width: crossSize, scaleX: squeeze, opacity }
      : { left: start, width: length, top: crossStart, height: crossSize, scaleY: squeeze, opacity }

  return (
    <motion.span
      aria-hidden
      className={cn('pointer-events-none absolute rounded-full', className)}
      style={style}
    />
  )
}
