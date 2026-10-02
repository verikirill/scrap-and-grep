import clsx from 'clsx'
import { ChevronDown } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router'
import { EASE, rowMotion } from '../../components/tokens'
import { Chip, ReadingTime } from '../../components/ui'
import type { FeedItem, Placement, ReactionKind } from '../../lib/api'
import { CATEGORY_LABELS, formatRelative } from '../../lib/format'
import { useSeen } from '../../lib/impressions'
import { OriginalLink } from '../reader/OriginalLink'
import { articlePath } from '../reader/paths'
import { RejectedRow, WhyPanel } from './cardParts'
import { ReactionBar } from './ReactionBar'
import { hasBreakdown, reasonIcon } from './reasons'

export type FeedCardProps = {
  item: FeedItem
  index: number
  placement: Placement
  onReact: (kind: ReactionKind, isActive: boolean) => void
}

/** One article of the feed: what it is, why it is here, and the reader's verdict. */
export function FeedCard({ item, index, placement, onReact }: FeedCardProps) {
  const [isWhyOpen, setIsWhyOpen] = useState(false)
  // Scrolled past without a mark is a quiet "not this": adaptive profiles learn from it.
  const seenRef = useSeen(item.article_id, 'feed', item.reactions.length === 0, placement)
  const isRejected = item.reactions.includes('hide') || item.reactions.includes('dislike')
  const isRead = item.reactions.includes('open')
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
      <div className="mt-1.5 flex items-start gap-1">
        <Link
          to={articlePath(item.article_id)}
          onClick={markRead}
          // A middle click opens a tab too, without a click event.
          onAuxClick={(event) => {
            // The middle button opens a tab; the right one only a menu.
            if (event.button === 1) markRead()
          }}
          className={clsx(
            'min-w-0 flex-1 font-serif text-[18px] leading-snug font-semibold decoration-primary/40 underline-offset-4 hover:underline',
            isRead ? 'text-muted-foreground' : 'text-foreground',
          )}
        >
          {item.title}
        </Link>
        <OriginalLink url={item.url} title={item.title} onOpen={markRead} />
      </div>
      {item.summary && (
        <p className="mt-2 line-clamp-3 text-sm text-foreground/85">{item.summary}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          {item.reasons.map((reason) => {
            const Icon = reasonIcon(reason.kind)
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
          {hasBreakdown(item) && (
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
