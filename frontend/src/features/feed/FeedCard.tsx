import clsx from 'clsx'
import {
  BriefcaseBusiness,
  ChevronDown,
  Compass,
  ExternalLink,
  Heart,
  Rss,
  Target,
  Users,
} from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { EASE, rowMotion } from '../../components/tokens'
import { Chip, ReadingTime } from '../../components/ui'
import type { FeedItem, FeedReason, ReactionKind } from '../../lib/api'
import { CATEGORY_LABELS, externalHref, formatRelative } from '../../lib/format'
import { useSeen } from '../../lib/impressions'
import { ReactionBar } from './ReactionBar'

const REASON_ICONS: Record<FeedReason['kind'], IconComponent> = {
  interest: Target,
  resume: BriefcaseBusiness,
  learned: Heart,
  collab: Users,
  source: Rss,
  explore: Compass,
}

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

function WhyPanel({ item }: { item: FeedItem }) {
  const rows = PARTS.filter(([key]) => Math.abs(item.parts[key] ?? 0) >= 0.005)
  return (
    <dl className="mt-3 grid gap-x-6 gap-y-1.5 rounded-xl bg-surface-container px-4 py-3 text-xs sm:grid-cols-2">
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
  )
}

type Props = {
  item: FeedItem
  index: number
  onReact: (kind: ReactionKind, isActive: boolean) => void
}

/**
 * What is left of a card the reader hid or disliked. It stays in place until
 * the feed is rebuilt, so the verdict can be taken back.
 */
function RejectedRow({ item, onReact }: Omit<Props, 'index'>) {
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
      className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-outline-variant px-4 py-2.5 text-sm text-muted-foreground"
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

/** One article of the feed: what it is, why it is here, and the reader's verdict. */
export function FeedCard({ item, index, onReact }: Props) {
  const [isWhyOpen, setIsWhyOpen] = useState(false)
  // Scrolled past without a mark is a quiet "not this": adaptive profiles learn from it.
  const seenRef = useSeen(item.article_id, 'feed', item.reactions.length === 0)
  const isRejected = item.reactions.includes('hide') || item.reactions.includes('dislike')
  const isRead = item.reactions.includes('open')
  const hasBreakdown = Object.keys(item.parts).length > 0 && !item.explore
  const markRead = () => {
    if (!isRead) onReact('open', true)
  }

  if (isRejected) return <RejectedRow item={item} onReact={onReact} />

  return (
    <motion.article
      ref={seenRef}
      {...rowMotion(index)}
      className="group rounded-2xl border border-outline-variant bg-card px-5 py-4 shadow-card transition-colors duration-200 hover:border-outline"
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{item.source_name}</span>
        <span>{CATEGORY_LABELS[item.source_category] ?? item.source_category}</span>
        <span>{formatRelative(item.published_at)}</span>
        <ReadingTime minutes={item.reading_minutes} />
        {isRead && <span className="text-outline">прочитано</span>}
      </div>
      <a
        href={externalHref(item.url)}
        target="_blank"
        rel="noopener noreferrer"
        onClick={markRead}
        // A middle click opens a tab too, without a click event.
        onAuxClick={markRead}
        className={clsx(
          'mt-1.5 block font-serif text-[18px] leading-snug font-semibold decoration-primary/40 underline-offset-4 hover:underline',
          isRead ? 'text-muted-foreground' : 'text-foreground',
        )}
      >
        {item.title}
        <ExternalLink
          size={13}
          className="ml-1.5 inline -translate-y-px text-outline opacity-0 transition-opacity group-hover:opacity-100"
        />
      </a>
      {item.summary && (
        <p className="mt-2 line-clamp-3 text-sm text-foreground/85">{item.summary}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          {item.reasons.map((reason) => {
            const Icon = REASON_ICONS[reason.kind] ?? Target
            return (
              <Chip
                key={`${reason.kind}-${reason.text}`}
                tone={
                  reason.kind === 'explore'
                    ? 'spark'
                    : reason.kind === 'interest'
                      ? 'accent'
                      : 'neutral'
                }
                className="max-w-full"
              >
                <Icon size={12} className="shrink-0" />
                <span className="truncate">{reason.text}</span>
              </Chip>
            )
          })}
          {hasBreakdown && (
            <button
              type="button"
              onClick={() => setIsWhyOpen((value) => !value)}
              aria-expanded={isWhyOpen}
              className="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs text-outline hover:text-foreground"
            >
              {item.score.toFixed(2)}
              <motion.span animate={{ rotate: isWhyOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={13} />
              </motion.span>
              <span className="sr-only">Из чего сложилась оценка</span>
            </button>
          )}
        </div>
        <ReactionBar reactions={item.reactions} subject={item.title} onReact={onReact} />
      </div>

      <AnimatePresence initial={false}>
        {isWhyOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: EASE }}
            className="overflow-hidden"
          >
            <WhyPanel item={item} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}
