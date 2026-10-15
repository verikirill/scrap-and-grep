import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown } from '../../components/icons'
import { EASE } from '../../components/tokens'

/**
 * A setting folded under one line: its title and a summary of the choice,
 * opened to a note and the choices themselves.
 */
export function FoldedPicker({
  title,
  summary,
  note,
  children,
}: {
  title: string
  summary: string
  note: string
  children: ReactNode
}) {
  const [isOpen, setOpen] = useState(false)
  const panelId = useId()
  return (
    <div className="rounded-xl border border-separator">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{title}</span>
          <span className="mt-0.5 block text-xs text-muted">{summary}</span>
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={17} className="text-muted" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: EASE }}
            className="overflow-hidden"
          >
            <div className="space-y-3.5 border-t border-separator px-3.5 py-3">
              <p className="text-xs text-muted">{note}</p>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** One choice as a chip with a tick box: ticked is shown. */
export function ShowChip({
  label,
  isShown,
  onChange,
}: {
  label: string
  isShown: boolean
  onChange: (isShown: boolean) => void
}) {
  return (
    <label
      className={clsx(
        'inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] transition-colors duration-150',
        isShown
          ? 'border-accent bg-accent-soft text-accent-soft-foreground'
          : 'border-separator text-muted hover:border-border hover:text-foreground',
      )}
    >
      <input
        type="checkbox"
        checked={isShown}
        onChange={(event) => onChange(event.target.checked)}
        className="size-3.5 shrink-0 accent-accent"
      />
      {label}
    </label>
  )
}
