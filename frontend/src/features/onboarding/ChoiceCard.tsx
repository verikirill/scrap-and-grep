import clsx from 'clsx'
import type { ReactNode, Ref } from 'react'
import { Check } from '../../components/icons'

type Props = {
  isChosen: boolean
  onChoose: () => void
  /** A picture on the left: an icon or a profile's tile. */
  leading: ReactNode
  title: string
  children: ReactNode
  /** From useRadioKeys: one Tab stop for the group, arrows move the choice. */
  ref?: Ref<HTMLButtonElement>
  tabIndex?: number
}

/** One option of a radio group drawn as a card, as the resume topics are drawn. */
export function ChoiceCard({ isChosen, onChoose, leading, title, children, ...rest }: Props) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={isChosen}
      onClick={onChoose}
      className={clsx(
        'flex w-full min-w-0 items-start gap-3 rounded-2xl border p-4 text-left transition-colors duration-150',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
        isChosen
          ? 'border-accent/50 bg-accent-soft/50'
          : 'border-separator bg-surface hover:border-border',
      )}
      {...rest}
    >
      {leading}
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold break-words">{title}</span>
        <span className="mt-0.5 block text-sm text-muted">{children}</span>
      </span>
      <span
        aria-hidden
        className={clsx(
          'mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border transition-colors duration-150',
          isChosen ? 'border-accent bg-accent text-white dark:text-[#0b0f17]' : 'border-separator',
        )}
      >
        {isChosen && <Check size={13} />}
      </span>
    </button>
  )
}
