import clsx from 'clsx'
import { Bookmark, EyeOff, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { motion } from 'motion/react'
import type { ReactionKind } from '../../lib/api'

type Action = {
  kind: ReactionKind
  icon: LucideIcon
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
    activeClass: 'bg-ok-soft text-ok',
  },
  {
    kind: 'dislike',
    icon: ThumbsDown,
    label: 'Меньше такого',
    activeLabel: 'Убрать отметку «меньше такого»',
    activeClass: 'bg-danger-soft text-danger',
  },
  {
    kind: 'save',
    icon: Bookmark,
    label: 'Сохранить',
    activeLabel: 'Убрать из сохранённого',
    activeClass: 'bg-spark-soft text-spark',
  },
  {
    kind: 'hide',
    icon: EyeOff,
    label: 'Скрыть',
    activeLabel: 'Вернуть в ленту',
    activeClass: 'bg-sunken text-text',
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
  className?: string
}

/** Like, dislike, save and hide. Each button is a toggle and says so to a screen reader. */
export function ReactionBar({
  reactions,
  subject,
  onReact,
  canHide = true,
  isDisabled = false,
  className,
}: Props) {
  const actions = canHide ? ACTIONS : ACTIONS.filter((action) => action.kind !== 'hide')
  return (
    <div className={clsx('flex items-center gap-0.5', className)}>
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
              'grid size-8 place-items-center rounded-lg transition-colors duration-150 disabled:opacity-40',
              isActive ? activeClass : 'text-faint hover:bg-sunken hover:text-text',
            )}
          >
            <Icon size={16} fill={isActive && kind !== 'hide' ? 'currentColor' : 'none'} />
          </motion.button>
        )
      })}
    </div>
  )
}
