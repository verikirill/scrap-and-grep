import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useId, useState } from 'react'
import { ChevronDown } from '../../components/icons'
import { EASE } from '../../components/tokens'
import { CARD_FIELD_GROUPS, withHidden } from '../../lib/cardFields'
import type { CardFieldKey } from '../../lib/cardFields'
import { plural } from '../../lib/format'

/** "все показаны" or "скрыто 3 поля": the setting at a glance, while folded. */
function shownSummary(hidden: number): string {
  if (hidden === 0) return 'все показаны'
  return `скрыто ${hidden} ${plural(hidden, ['поле', 'поля', 'полей'])}`
}

/**
 * Which rows of the attack and vulnerability cards the reader sees, folded
 * under one line. A ticked row is shown; all are by default. The headline,
 * the summary, the priority and "Почему это важно" are not in the list: they
 * always stay.
 */
export function CardFieldsPicker({
  hidden,
  onChange,
}: {
  hidden: readonly CardFieldKey[]
  onChange: (next: CardFieldKey[]) => void
}) {
  const [isOpen, setOpen] = useState(false)
  const panelId = useId()
  const hiddenSet = new Set(hidden)
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
          <span className="block text-sm font-medium">Поля карточек</span>
          <span className="mt-0.5 block text-xs text-muted">{shownSummary(hidden.length)}</span>
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
              <p className="text-xs text-muted">
                Снимите галочку, чтобы поле не показывалось в выпуске, файлах и письме. Заголовок,
                краткое содержание, приоритет и «Почему это важно» видны всегда.
              </p>
              {CARD_FIELD_GROUPS.map((group) => (
                <fieldset key={group.kind}>
                  <legend className="mb-1.5 text-[13px] font-medium">{group.title}</legend>
                  <div className="flex flex-wrap gap-1.5">
                    {group.fields.map((field) => {
                      const isShown = !hiddenSet.has(field.key)
                      return (
                        <label
                          key={field.key}
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
                            onChange={(event) =>
                              onChange(withHidden(hidden, field.key, !event.target.checked))
                            }
                            className="size-3.5 shrink-0 accent-accent"
                          />
                          {field.label}
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
