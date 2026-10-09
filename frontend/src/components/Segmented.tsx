import clsx from 'clsx'
import { motion } from 'motion/react'
import { useRadioKeys } from './useRadioKeys'

/**
 * One choice of a few, drawn as HeroUI's tabs: a grey track, the chosen one on
 * a raised pill that slides to the next choice.
 * A radio group for the keyboard: one Tab stop, arrows move the choice.
 * `isScrollable` lets any number of options scroll sideways instead of
 * squeezing into equal parts. A value that is none of the options leaves
 * nothing tinted (a choice made elsewhere, such as custom dates).
 */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  isScrollable = false,
  className,
}: {
  value: T
  /** `short` replaces the label on a phone, where five long labels do not fit. */
  options: readonly { value: T; label: string; short?: string }[]
  onChange: (value: T) => void
  label: string
  isScrollable?: boolean
  className?: string
}) {
  const found = options.findIndex((option) => option.value === value)
  const keys = useRadioKeys(options.length, found, (index) => onChange(options[index].value))

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={keys.onKeyDown}
      className={clsx(
        'relative isolate flex rounded-full bg-default p-1',
        // A fade at the right edge says there is more to scroll to.
        isScrollable &&
          'overflow-x-auto [mask-image:linear-gradient(to_right,black_85%,transparent)] [scrollbar-width:none]',
        className,
      )}
    >
      {options.map((option, index) => {
        const isChosen = index === found
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isChosen}
            {...keys.itemProps(index)}
            onClick={() => onChange(option.value)}
            className={clsx(
              'relative h-8 rounded-full px-2.5 text-[13px] font-medium transition-colors duration-200 outline-none sm:px-3.5',
              'focus-visible:ring-2 focus-visible:ring-focus',
              isScrollable ? 'flex-none' : 'flex-auto',
              isChosen ? 'text-foreground' : 'text-muted hover:text-foreground',
            )}
          >
            {isChosen && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.15 }}
                className="absolute inset-0 -z-10 rounded-full bg-surface shadow-surface"
              />
            )}
            {option.short ? (
              <>
                <span className="block whitespace-nowrap sm:hidden">{option.short}</span>
                <span className="hidden whitespace-nowrap sm:block">{option.label}</span>
              </>
            ) : (
              <span className="block truncate">{option.label}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
