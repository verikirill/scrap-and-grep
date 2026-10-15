import { DURATION, EASE } from '../../components/tokens'

/** A part that appears inside a step, such as the form of the chosen way. */
export const REVEAL = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: DURATION.medium, ease: EASE },
}

/**
 * A step comes in from the side the reader is heading to and the old one
 * leaves the other way. Under "reduce motion" only the fade is left.
 */
export const SLIDE = {
  variants: {
    enter: (direction: number) => ({ opacity: 0, x: direction * 28 }),
    center: { opacity: 1, x: 0 },
    exit: (direction: number) => ({ opacity: 0, x: direction * -20 }),
  },
  initial: 'enter',
  animate: 'center',
  exit: 'exit',
  transition: { duration: DURATION.medium, ease: EASE },
} as const

/** The parts of a preview rise one after another, as cards do on a fresh page. */
export function rise(index: number) {
  return {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: DURATION.long, ease: EASE, delay: 0.12 + index * 0.07 },
  }
}
