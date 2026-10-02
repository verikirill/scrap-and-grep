import clsx from 'clsx'
import { motion } from 'motion/react'
import { useEffect, useRef } from 'react'
import type { FeedItem, FeedReason, ReactionKind } from '../../lib/api'
import { hasBreakdown, reasonIcon } from './reasons'

// Parts of the score in the order they are explained, with a plain name each.
const PARTS: [string, string][] = [
  ['interest', 'Совпадение с интересами'],
  ['resume', 'Близость к опыту из резюме'],
  ['learned', 'Похоже на то, что вы отмечали'],
  ['fresh', 'Свежесть'],
  ['source', 'Отношение к источнику'],
  ['collab', 'Читают коллеги'],
  ['avoid', 'Близко к тому, что вы скрывали'],
  ['read', 'Уже открывали'],
]

const MATCH_PARTS = new Set(['interest', 'resume', 'learned'])

/** What the score is made of, under the `reasons` not shown elsewhere. */
export function WhyPanel({ item, reasons = [] }: { item: FeedItem; reasons?: FeedReason[] }) {
  const rows = PARTS.filter(([key]) => Math.abs(item.parts[key] ?? 0) >= 0.005)
  return (
    <div className="mt-3 space-y-2.5 rounded-xl bg-surface-container px-4 py-3 text-xs">
      {reasons.length > 0 && (
        <ul className="space-y-1.5">
          {reasons.map((reason, index) => {
            const Icon = reasonIcon(reason.kind)
            return (
              <li key={`${index}-${reason.kind}`} className="flex items-start gap-2">
                <Icon size={13} className="mt-px shrink-0 text-muted-foreground" />
                <span>{reason.text}</span>
              </li>
            )
          })}
        </ul>
      )}
      {hasBreakdown(item) && (
        <dl
          className={clsx(
            'grid gap-x-6 gap-y-1.5 sm:grid-cols-2',
            reasons.length > 0 && 'border-t border-outline-variant pt-2.5',
          )}
        >
          {rows.map(([key, label]) => {
            const value = item.parts[key] ?? 0
            // Matches are shown as they are (0..1); the rest are corrections to the
            // score and carry a sign.
            const text = MATCH_PARTS.has(key)
              ? value.toFixed(2)
              : `${value > 0 ? '+' : ''}${value.toFixed(2)}`
            return (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <dt className="text-muted-foreground">{label}</dt>
                <dd
                  className={clsx(
                    'tabular font-semibold',
                    value < 0 ? 'text-destructive' : 'text-foreground',
                  )}
                >
                  {text}
                </dd>
              </div>
            )
          })}
          <div className="flex items-baseline justify-between gap-3 border-t border-outline-variant pt-1.5 sm:col-span-2">
            <dt className="font-medium text-foreground">Итоговая оценка</dt>
            <dd className="tabular font-semibold text-foreground">{item.score.toFixed(2)}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}

type RejectedProps = {
  item: FeedItem
  onReact: (kind: ReactionKind, isActive: boolean) => void
  /** A post of the Telegram look leaves a service line in the middle, as a chat does. */
  look?: 'card' | 'service'
}

/**
 * What is left of an article the reader hid or disliked. It stays in place
 * until the feed is rebuilt, so the verdict can be taken back.
 */
export function RejectedRow({ item, onReact, look = 'card' }: RejectedProps) {
  const undo = useRef<HTMLButtonElement>(null)
  const isDisliked = item.reactions.includes('dislike')
  // The button that was pressed is gone with the card; without this, focus
  // would fall to the page and a keyboard user would lose their place.
  useEffect(() => {
    if (document.activeElement === document.body) undo.current?.focus()
  }, [])
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={clsx(
        'flex items-center gap-3 text-sm',
        look === 'service'
          ? 'mx-auto w-fit max-w-full rounded-full bg-on-surface/10 px-4 py-1.5 text-xs text-foreground/80 backdrop-blur'
          : 'justify-between rounded-xl border border-dashed border-outline-variant px-4 py-2.5 text-muted-foreground',
      )}
    >
      <span role="status" className="min-w-0 truncate">
        {isDisliked ? 'Меньше такого: ' : 'Скрыто: '}
        {item.title}
      </span>
      <button
        ref={undo}
        type="button"
        onClick={() => onReact(isDisliked ? 'dislike' : 'hide', false)}
        className="shrink-0 font-medium text-on-primary-container hover:underline"
      >
        Вернуть
      </button>
    </motion.div>
  )
}
