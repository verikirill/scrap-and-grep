import { useRef } from 'react'
import type { KeyboardEvent } from 'react'

// Keys that move the choice, as a radio group does: by one, or to an end.
const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

/**
 * The keyboard of a radio group: one Tab stop (the chosen item, or the first
 * when nothing is chosen), arrows and Home/End move the choice and the focus.
 */
export function useRadioKeys(count: number, chosen: number, onChoose: (index: number) => void) {
  const items = useRef<(HTMLElement | null)[]>([])
  const stop = Math.max(0, chosen)

  const choose = (index: number) => {
    const next = (index + count) % count
    onChoose(next)
    items.current[next]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key in STEP) choose(stop + STEP[event.key])
    else if (event.key === 'Home') choose(0)
    else if (event.key === 'End') choose(count - 1)
    else return
    event.preventDefault()
  }

  const itemProps = (index: number) => ({
    ref: (node: HTMLElement | null) => {
      items.current[index] = node
    },
    tabIndex: index === stop ? 0 : -1,
  })

  return { items, onKeyDown, itemProps }
}
