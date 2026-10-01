import clsx from 'clsx'
import { useRef } from 'react'
import { LiquidIndicator } from './LiquidIndicator'
import { useRadioKeys } from './useRadioKeys'

/**
 * Material 3 segmented button: one choice of a few. The chosen one is tinted,
 * and the tint flows to the next choice like a drop.
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
  const group = useRef<HTMLDivElement>(null)
  const found = options.findIndex((option) => option.value === value)
  const keys = useRadioKeys(options.length, found, (index) => onChange(options[index].value))

  return (
    <div
      ref={group}
      role="radiogroup"
      aria-label={label}
      onKeyDown={keys.onKeyDown}
      className={clsx(
        'relative isolate flex rounded-full border border-outline-variant bg-surface-container-low p-1',
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
              'relative h-9 rounded-full px-2.5 text-[13px] transition-colors duration-300 sm:px-3.5',
              isScrollable ? 'flex-none' : 'flex-auto',
              isChosen
                ? 'font-semibold text-primary-foreground'
                : 'font-medium text-on-surface-variant hover:text-on-surface',
            )}
          >
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
      {/* Last, so the buttons have handed over their elements when it measures. */}
      <LiquidIndicator
        container={group}
        targetKey={found >= 0 ? String(value) : null}
        getTarget={() => (found >= 0 ? keys.items.current[found] : null)}
        axis="x"
        className="-z-10 bg-primary shadow-elevation-1"
      />
    </div>
  )
}
