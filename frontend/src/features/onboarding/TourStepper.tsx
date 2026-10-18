import clsx from 'clsx'
import { motion } from 'motion/react'
import type { IconComponent } from '../../components/icons'
import { DURATION, EASE } from '../../components/tokens'

export type StepMark = {
  key: string
  /** Its name on the stepper. */
  label: string
  icon: IconComponent
}

type Props = {
  steps: readonly StepMark[]
  current: number
  /** Whether a step may be opened from here; a closed one is drawn but not pressable. */
  canOpen: (index: number) => boolean
  onOpen: (index: number) => void
}

/**
 * Where the reader is in the tour: a thin segment per step, the current one in
 * the accent, and above them the step's icon, name and number.
 * A segment opens its step, as dots under a slideshow do.
 */
export function TourStepper({ steps, current, canOpen, onOpen }: Props) {
  const step = steps[current]
  return (
    <nav aria-label="Шаги знакомства">
      <div className="flex items-center gap-2.5">
        <motion.span
          key={step.key}
          aria-hidden
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: DURATION.medium, ease: EASE }}
          className="icon-tile grid size-8 shrink-0 place-items-center rounded-[10px]"
        >
          <step.icon size={16} />
        </motion.span>
        <p className="min-w-0 text-sm">
          <span className="font-semibold">{step.label}</span>
          <span className="tabular text-muted">
            {' '}
            · шаг {current + 1} из {steps.length}
          </span>
        </p>
      </div>
      <ol className="mt-3 flex gap-1">
        {steps.map((item, index) => {
          const isOpenable = canOpen(index) && index !== current
          return (
            <li key={item.key} className="min-w-0 flex-1">
              <button
                type="button"
                aria-label={`Шаг ${index + 1}: ${item.label}`}
                aria-current={index === current ? 'step' : undefined}
                disabled={!isOpenable && index !== current}
                onClick={() => isOpenable && onOpen(index)}
                className={clsx(
                  'group block w-full py-2 focus-visible:outline-offset-0',
                  !isOpenable && 'cursor-default',
                )}
              >
                <span
                  className={clsx(
                    'relative block h-1.5 overflow-hidden rounded-full transition-colors duration-300',
                    index < current ? 'bg-accent/45' : 'bg-default',
                    isOpenable && 'group-hover:bg-accent/60',
                  )}
                >
                  {index === current && (
                    <motion.span
                      layoutId="tour-stepper-current"
                      transition={{ duration: DURATION.medium, ease: EASE }}
                      className="absolute inset-0 rounded-full bg-accent"
                    />
                  )}
                </span>
                <span
                  className={clsx(
                    'mt-1.5 hidden truncate text-[11px] leading-tight md:block',
                    index === current ? 'font-semibold text-foreground' : 'text-muted',
                  )}
                >
                  {item.label}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
