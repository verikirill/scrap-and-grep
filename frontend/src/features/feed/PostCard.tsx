import clsx from 'clsx'
import { ChevronDown, Eye, Target } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router'
import { EASE, rowMotion } from '../../components/tokens'
import { ReadingTime } from '../../components/ui'
import { api } from '../../lib/api'
import { CATEGORY_LABELS, formatPostTime } from '../../lib/format'
import { useSeen } from '../../lib/impressions'
import { OriginalLink } from '../reader/OriginalLink'
import { articlePath } from '../reader/paths'
import { RejectedRow, WhyPanel } from './cardParts'
import type { FeedCardProps } from './FeedCard'
import { ReactionBar } from './ReactionBar'
import { REASON_ICONS, hasBreakdown } from './reasons'
import { SourceAvatar } from './SourceAvatar'
import { sourceTint } from './sourceLook'

/**
 * One article as a post in a Telegram channel: the source with its avatar,
 * the article's picture, its headline and summary, one reason, and the
 * reader's verdict as reactions. The other reasons and the score open on tap.
 */
export function PostCard({ item, index, isQuiet, placement, onReact }: FeedCardProps) {
  const [isWhyOpen, setIsWhyOpen] = useState(false)
  // A picture the site would not give leaves a post of text, until the feed is reloaded.
  const [isPictureBroken, setIsPictureBroken] = useState(false)
  const hasPicture = item.has_picture && !isPictureBroken
  const seenRef = useSeen(item.article_id, 'feed', item.reactions.length === 0, placement)
  const isRejected = item.reactions.includes('hide') || item.reactions.includes('dislike')
  const isRead = item.reactions.includes('open')
  const markRead = () => {
    if (!isRead) onReact('open', true)
  }
  // A middle click opens a tab without a click event; the right one only a menu.
  const markReadOnAux = (event: React.MouseEvent) => {
    if (event.button === 1) markRead()
  }

  if (isRejected) return <RejectedRow item={item} onReact={onReact} look="service" />

  const [reason, ...otherReasons] = item.reasons
  const ReasonIcon = reason ? (REASON_ICONS[reason.kind] ?? Target) : null
  const canExplain = otherReasons.length > 0 || hasBreakdown(item)
  const tint = sourceTint(item.source_id)

  return (
    <motion.article
      ref={seenRef}
      {...rowMotion(index, isQuiet)}
      aria-label={item.title}
      className="group flex items-end sm:gap-2.5"
    >
      {/* On a phone the width goes to the text: the source is named in the post. */}
      <span className="hidden shrink-0 sm:block">
        <SourceAvatar
          sourceId={item.source_id}
          name={item.source_name}
          className="size-10 text-sm"
        />
      </span>
      {/* Without the wallpaper of a phone, a light bubble is a white card on the grey page. */}
      <div className="min-w-0 flex-1 overflow-hidden rounded-2xl rounded-bl-md bg-background shadow-[0_1px_2px_rgb(0_0_0/0.13)] sm:not-dark:bg-surface sm:not-dark:shadow-surface dark:bg-surface-tertiary">
        {hasPicture && (
          // The headline below is the link a screen reader and the keyboard use.
          <Link
            to={articlePath(item.article_id)}
            onClick={markRead}
            onAuxClick={markReadOnAux}
            tabIndex={-1}
            aria-hidden
            className="block bg-surface-secondary"
          >
            <img
              src={api.articlePictureUrl(item.article_id)}
              alt=""
              loading={index < 2 ? 'eager' : 'lazy'}
              decoding="async"
              onError={() => setIsPictureBroken(true)}
              className="aspect-video w-full object-cover"
            />
          </Link>
        )}

        <div className="px-3.5 pt-2.5 pb-2 sm:px-4">
          <div className="flex items-center gap-2 text-[13px]">
            <span
              className="min-w-0 truncate font-semibold"
              style={{ color: `var(--on-tag-${tint})` }}
            >
              {item.source_name}
            </span>
            <span className="shrink-0 text-muted">
              {CATEGORY_LABELS[item.source_category] ?? item.source_category}
            </span>
            <span className="ml-auto flex shrink-0 items-center text-muted">
              <OriginalLink url={item.url} title={item.title} onOpen={markRead} />
            </span>
          </div>

          <Link
            to={articlePath(item.article_id)}
            onClick={markRead}
            onAuxClick={markReadOnAux}
            className={clsx(
              'mt-1 block text-[16px] leading-snug font-semibold decoration-accent/40 underline-offset-4 hover:underline',
              isRead ? 'text-muted' : 'text-foreground',
            )}
          >
            {item.title}
          </Link>
          {item.summary && (
            <p className="mt-1 text-[15px] leading-relaxed text-foreground/90">{item.summary}</p>
          )}

          {reason && ReasonIcon && canExplain && (
            <button
              type="button"
              onClick={() => setIsWhyOpen((value) => !value)}
              aria-expanded={isWhyOpen}
              className="mt-2 flex max-w-full items-center gap-1.5 rounded-md text-left text-xs text-muted hover:text-foreground"
            >
              <ReasonIcon size={13} className="shrink-0" />
              <span className="truncate">{reason.text}</span>
              {otherReasons.length > 0 && (
                <span className="shrink-0 text-muted">и ещё {otherReasons.length}</span>
              )}
              <motion.span
                animate={{ rotate: isWhyOpen ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="shrink-0"
              >
                <ChevronDown size={13} />
              </motion.span>
              <span className="sr-only">Причины подбора статьи</span>
            </button>
          )}
          {reason && ReasonIcon && !canExplain && (
            // Nothing more to show: the reason is text, whole on hover when cut.
            <p
              title={reason.text}
              className="mt-2 flex max-w-full items-center gap-1.5 text-xs text-muted"
            >
              <ReasonIcon size={13} className="shrink-0" />
              <span className="truncate">{reason.text}</span>
            </p>
          )}
          <AnimatePresence initial={false}>
            {isWhyOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="overflow-hidden"
              >
                <WhyPanel item={item} reasons={otherReasons} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* On a narrow phone the time goes under the reactions rather than off the edge. */}
          <div className="mt-2.5 flex flex-wrap items-end justify-between gap-x-2 gap-y-1.5">
            <ReactionBar
              reactions={item.reactions}
              subject={item.title}
              onReact={onReact}
              look="pills"
            />
            <span className="ml-auto flex shrink-0 items-center gap-2 pb-0.5 text-[12px] text-muted">
              <ReadingTime minutes={item.reading_minutes} />
              {isRead && <Eye size={13} aria-label="Прочитано" />}
              <time dateTime={item.published_at}>{formatPostTime(item.published_at)}</time>
            </span>
          </div>
        </div>
      </div>
    </motion.article>
  )
}
