import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { ArrowUp } from './icons'
import { DURATION, EASE } from './tokens'

// Shown once the reader is this far down: a screen or so of a long text.
const SHOW_AFTER_PX = 700

/**
 * A round button that takes a long page back to its top. It floats over the
 * text once the top is out of reach, above the phone's navigation bar.
 */
export function ScrollTopButton() {
  const [isShown, setIsShown] = useState(false)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    let frame = 0
    const check = () => {
      frame = 0
      setIsShown(window.scrollY > SHOW_AFTER_PX)
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(check)
    }
    check()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <AnimatePresence>
      {isShown && (
        <motion.button
          type="button"
          initial={{ opacity: 0, scale: 0.8, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.8, y: 8 }}
          transition={{ duration: DURATION.short, ease: EASE }}
          whileTap={{ scale: 0.92 }}
          onClick={() => window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' })}
          aria-label="Наверх"
          title="Наверх"
          className="state-layer fixed right-4 bottom-[calc(6rem+env(safe-area-inset-bottom))] z-20 grid size-12 place-items-center overflow-hidden rounded-2xl bg-primary-container text-on-primary-container shadow-elevation-2 md:right-8 md:bottom-8"
        >
          <ArrowUp size={22} />
        </motion.button>
      )}
    </AnimatePresence>
  )
}
