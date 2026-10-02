import clsx from 'clsx'
import { Bookmark, EyeOff, ThumbsDown, ThumbsUp } from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import { motion } from 'motion/react'
import type { ReactionKind } from '../../lib/api'

type Action = {
  kind: ReactionKind
  icon: IconComponent
  label: string
  activeLabel: string
  activeClass: string
}

const ACTIONS: Action[] = [
  {
    kind: 'like',
    icon: ThumbsUp,
    label: 'Больше такого',
    activeLabel: 'Убрать отметку «больше такого»',
    activeClass: 'bg-success-container text-success',
  },
  {
    kind: 'dislike',
    icon: ThumbsDown,
    label: 'Меньше такого',
    activeLabel: 'Убрать отметку «меньше такого»',
    activeClass: 'bg-error-container text-destructive',
  },
  {
    kind: 'save',
    icon: Bookmark,
    label: 'Сохранить',
    activeLabel: 'Убрать из сохранённого',
    activeClass: 'bg-spark-container text-spark',
  },
  {
    kind: 'hide',
    icon: EyeOff,
    label: 'Скрыть',
    activeLabel: 'Вернуть в ленту',
    activeClass: 'bg-surface-container text-foreground',
  },
]

type Props = {
  reactions: ReactionKind[]
  /** The article the buttons act on, so a screen reader can tell them apart. */
  subject: string
  onReact: (kind: ReactionKind, isActive: boolean) => void
  /** Hiding makes sense in a feed; a digest keeps every selected item in place. */
  canHide?: boolean
  isDisabled?: boolean
  /** Square icons, or round pills under a post as Telegram draws reactions. */
  look?: 'icons' | 'pills'
  className?: string
}

/** Like, dislike, save and hide. Each button is a toggle and says so to a screen reader. */
export function ReactionBar({
  reactions,
  subject,
  onReact,
  canHide = true,
  isDisabled = false,
  look = 'icons',
  className,
}: Props) {
  const actions = canHide ? ACTIONS : ACTIONS.filter((action) => action.kind !== 'hide')
  return (
    <div className={clsx('flex items-center', look === 'pills' ? 'gap-1.5' : 'gap-0.5', className)}>
      {actions.map(({ kind, icon: Icon, label, activeLabel, activeClass }) => {
        const isActive = reactions.includes(kind)
        return (
          <motion.button
            key={kind}
            type="button"
            whileTap={{ scale: 0.86 }}
            disabled={isDisabled}
            // The name stays the same and aria-pressed carries the state;
            // the tooltip may say what a second click does.
            aria-pressed={isActive}
            aria-label={`${label}: ${subject}`}
            title={isActive ? activeLabel : label}
            onClick={() => onReact(kind, !isActive)}
            className={clsx(
              'grid place-items-center transition-colors duration-150 disabled:opacity-40',
              // A finger needs 40 px; a mouse does with 32.
              look === 'pills'
                ? 'h-10 min-w-11 rounded-full px-3 md:h-8'
                : 'size-10 rounded-lg md:size-8',
              isActive
                ? activeClass
                : look === 'pills'
                  ? 'bg-primary/10 text-primary hover:bg-primary/15'
                  : 'text-outline hover:bg-surface-container hover:text-foreground',
            )}
          >
            <Icon size={16} fill={isActive && kind !== 'hide' ? 'currentColor' : 'none'} />
          </motion.button>
        )
      })}
    </div>
  )
}
