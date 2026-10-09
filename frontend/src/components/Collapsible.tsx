import { AnimatePresence, motion } from 'motion/react'
import { useId, useState, type ReactNode } from 'react'

import { readOpen, writeOpen } from '../lib/remembered'
import { ChevronDown } from './icons'
import { DURATION, EASE } from './tokens'

/**
 * A block whose body folds away under its head, smoothly, and stays as the
 * reader left it on the next visit. The head always shows, so it carries what
 * is worth seeing folded; the body takes the details.
 */
export function Collapsible({
  storageKey,
  title,
  head,
  children,
  defaultOpen = true,
}: {
  /** Where the fold is kept; one per kind of block, not per page. */
  storageKey: string
  /** The block's name for a screen reader: «Свернуть: <title>». */
  title: string
  head: ReactNode
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(() => readOpen(storageKey, defaultOpen))
  const bodyId = useId()
  const toggle = () => {
    const next = !isOpen
    setIsOpen(next)
    writeOpen(storageKey, next)
  }
  return (
    <>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">{head}</div>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={isOpen}
          aria-controls={bodyId}
          aria-label={`${isOpen ? 'Свернуть' : 'Развернуть'}: ${title}`}
          title={isOpen ? 'Свернуть' : 'Развернуть'}
          className="-my-1 -mr-1.5 grid size-9 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-accent/10 hover:text-accent"
        >
          <motion.span
            className="grid"
            animate={{ rotate: isOpen ? 180 : 0 }}
            transition={{ duration: DURATION.short, ease: EASE }}
          >
            <ChevronDown size={20} />
          </motion.span>
        </button>
      </div>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="body"
            id={bodyId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: DURATION.medium, ease: EASE }}
            className="overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
