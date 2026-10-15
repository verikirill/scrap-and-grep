import { useRef } from 'react'
import { cn } from '../lib/utils'
import type { IconComponent } from './icons'
import { SlidingPill } from './SlidingPill'
import { useRadioKeys } from './useRadioKeys'

type Option<T extends string> = {
  value: T
  label: string
  /** `short` replaces the label on a phone, where five long labels do not fit. */
  short?: string
  /** An icon before the label; `labelClassName` may hide the label and leave the icon. */
  icon?: IconComponent
}

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
  itemClassName,
  labelClassName,
}: {
  value: T
  options: readonly Option<T>[]
  onChange: (value: T) => void
  label: string
  isScrollable?: boolean
  className?: string
  /** Overrides for each option's button, such as a narrower padding. */
  itemClassName?: string
  /** Classes of the label beside an icon, such as hiding it where room is short. */
  labelClassName?: string
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
      className={cn(
        'relative isolate flex rounded-full bg-default p-1',
        // A fade at the right edge says there is more to scroll to.
        isScrollable &&
          'overflow-x-auto [mask-image:linear-gradient(to_right,black_85%,transparent)] [scrollbar-width:none]',
        className,
      )}
    >
      <SlidingPill
        container={group}
        activeKey={found >= 0 ? String(value) : null}
        className="rounded-full bg-surface shadow-surface"
      />
      {options.map((option, index) => {
        const isChosen = index === found
        const Icon = option.icon
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isChosen}
            data-active={isChosen}
            // With an icon the label may be hidden: the name and the hint stay.
            aria-label={Icon ? option.label : undefined}
            title={Icon ? option.label : undefined}
            {...keys.itemProps(index)}
            onClick={() => onChange(option.value)}
            className={cn(
              'relative h-8 rounded-full px-2.5 text-[13px] font-medium transition-colors duration-200 outline-none sm:px-3.5',
              'focus-visible:ring-2 focus-visible:ring-focus',
              isScrollable ? 'flex-none' : 'flex-auto',
              Icon && 'inline-flex items-center justify-center gap-1.5',
              isChosen ? 'text-foreground' : 'text-muted hover:text-foreground',
              itemClassName,
            )}
          >
            {Icon ? (
              <>
                <Icon size={16} className="shrink-0" />
                <span className={cn('whitespace-nowrap', labelClassName)}>{option.label}</span>
              </>
            ) : option.short ? (
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
