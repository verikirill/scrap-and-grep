import clsx from 'clsx'
import { motion } from 'motion/react'
import { useId, useRef } from 'react'
import type { KeyboardEvent } from 'react'

// Keys that move the choice, as a radio group does: by one, or to an end.
const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

/**
 * Material 3 segmented button: one choice of a few, the chosen one tinted.
 * A radio group for the keyboard: one Tab stop, arrows move the choice.
 * `isScrollable` lets any number of options scroll sideways instead of
 * squeezing into equal parts.
 */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  isScrollable = false,
}: {
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
  label: string
  isScrollable?: boolean
}) {
  const group = useId()
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const chosen = Math.max(
    0,
    options.findIndex((option) => option.value === value),
  )

  const choose = (index: number) => {
    const next = (index + options.length) % options.length
    onChange(options[next].value)
    buttons.current[next]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key in STEP) choose(chosen + STEP[event.key])
    else if (event.key === 'Home') choose(0)
    else if (event.key === 'End') choose(options.length - 1)
    else return
    event.preventDefault()
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={clsx(
        'flex rounded-full border border-outline p-0.5',
        isScrollable && 'overflow-x-auto [scrollbar-width:none]',
      )}
    >
      {options.map((option, index) => {
        const isChosen = option.value === value
        return (
          <button
            key={option.value}
            ref={(node) => {
              buttons.current[index] = node
            }}
            type="button"
            role="radio"
            aria-checked={isChosen}
            tabIndex={index === chosen ? 0 : -1}
            onClick={() => onChange(option.value)}
            className={clsx(
              'state-layer relative h-9 overflow-hidden rounded-full px-3 text-[13px] font-medium transition-colors',
              isScrollable ? 'flex-none' : 'min-w-0 flex-1',
              isChosen ? 'text-on-secondary-container' : 'text-on-surface-variant',
            )}
          >
            {isChosen && (
              <motion.span
                layoutId={`segment-${group}`}
                className="absolute inset-0 -z-10 rounded-full bg-secondary-container"
                transition={{ type: 'spring', stiffness: 520, damping: 40 }}
              />
            )}
            <span className="relative truncate">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}
