import { useEffect, useEffectEvent } from 'react'

type Handlers = {
  /** Arrow right, or Enter where it would press nothing else. Absent: no step ahead. */
  onNext?: () => void
  /** Arrow left. Absent: no step behind. */
  onBack?: () => void
  /** Escape. */
  onSkip: () => void
}

// Places that read these keys themselves: typing, a radio group, a dialog.
const OWN_KEYS =
  'input, textarea, select, [contenteditable="true"], [role="radiogroup"], [role="tablist"], [role="listbox"], [role="menu"], [role="slider"], [role="dialog"]'
// Enter already presses these.
const PRESSABLE = 'button, a[href], [role="button"], [role="radio"], [role="switch"], summary'

/**
 * The keys of the tour: arrows step back and forth, Enter goes on, Escape
 * skips. A field, a radio group or a dialog keeps its own keys, and Enter on a
 * button presses that button.
 */
export function useTourKeys({ onNext, onBack, onSkip }: Handlers) {
  const handle = useEffectEvent((event: KeyboardEvent) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return
    const target = event.target instanceof Element ? event.target : null
    if (target?.closest(OWN_KEYS)) return
    let action: (() => void) | undefined
    if (event.key === 'ArrowRight') action = onNext
    else if (event.key === 'ArrowLeft') action = onBack
    else if (event.key === 'Enter' && !event.shiftKey && !target?.closest(PRESSABLE)) {
      action = onNext
    } else if (event.key === 'Escape') action = onSkip
    if (!action) return
    event.preventDefault()
    action()
  })

  useEffect(() => {
    const listener = (event: KeyboardEvent) => handle(event)
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])
}
