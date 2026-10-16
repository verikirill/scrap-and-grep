import clsx from 'clsx'
import {
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  GitCompareArrows,
  Info,
} from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { buttonClass, EASE, rowMotion } from '../../components/tokens'
import { AnimatedNumber, Card, Chip, ScoreBar, ReadingTime } from '../../components/ui'
import { api } from '../../lib/api'
import type { Digest, DigestItem, Placement, ReactionKind, Topic } from '../../lib/api'
import { formatDate, formatDateTime, modelLabel, plural, REJECT_LABELS } from '../../lib/format'
import { useSeen } from '../../lib/impressions'
import { useFeedback, useMe, useReactions, useUpdateSettings } from '../../lib/queries'
import { firstEntries, foldSummary, withFolded } from '../../lib/folding'
import { REVEAL_EVENT } from '../../lib/entryNav'
import { isShown } from '../../lib/digestBlocks'
import type { DigestBlockKey } from '../../lib/digestBlocks'
import { ReactionBar } from '../feed/ReactionBar'
import { OriginalLink } from '../reader/OriginalLink'
import { articlePath } from '../reader/paths'
import { AskDigest } from './AskDigest'
import { CveTimeline } from './CveTimeline'
import { RiskMatrix } from './RiskMatrix'
import { BriefingPlayer } from './BriefingPlayer'
import { EntryDetails, PriorityChip, VerifiedBadge } from './EntryCard'
import { MailButton } from './MailButton'
import { IssueExtras, ManualWork } from './IssueExtras'
import { ShortPanel } from './ShortPanel'
import { StoryStack } from './StoryStack'
import { IndicatorsBlock, SocExport } from './ThreatIntel'

/** From the period's publications to the issue, as three small chips in one line. */
function Funnel({ digest }: { digest: Digest }) {
  const stats = digest.stats
  const steps = [
    { label: 'публикаций за период', value: stats.window_total ?? 0 },
    { label: 'кандидатов по интересам', value: stats.candidates ?? 0 },
    { label: 'в выпуске', value: stats.selected ?? 0 },
  ]
  return (
    <ul aria-label="Цифры выпуска" className="flex flex-wrap items-center gap-1.5 text-xs">
      {steps.map((step, index) => (
        <li key={step.label} className="flex items-center gap-1.5">
          {index > 0 && <ChevronRight size={12} aria-hidden className="text-muted" />}
          <span
            className={clsx(
              'inline-flex items-baseline gap-1 rounded-full px-2.5 py-1',
              index === 2 ? 'bg-warning-soft' : 'bg-surface-secondary',
            )}
          >
            <AnimatedNumber value={step.value} className="font-semibold text-foreground" />
            <span className="text-muted">{step.label}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

type ItemCardProps = {
  item: DigestItem
  index: number
  placement: Placement
  reactions: ReactionKind[] | undefined
  onReact: (kind: ReactionKind, isActive: boolean) => void
  /** The vulnerability's dated steps under the entry, unless the reader hides them. */
  hasTimeline: boolean
}

function ItemCard({ item, index, placement, reactions, onReact, hasTimeline }: ItemCardProps) {
  const translated = item.headline !== item.title
  const personal = Math.abs(item.personal) >= 0.005 ? item.personal : 0
  const seenRef = useSeen(item.article_id, 'digest', !reactions?.length, placement)
  const markRead = () => {
    if (reactions !== undefined && !reactions.includes('open')) onReact('open', true)
  }
  return (
    <motion.article
      ref={seenRef}
      id={`entry-${placement.position}`}
      {...rowMotion(index)}
      className="group scroll-mt-24 rounded-xl border border-separator bg-surface px-4 py-4"
    >
      <div className="flex items-start gap-1">
        <Link
          to={articlePath(item.article_id)}
          onClick={markRead}
          // A middle click opens a tab too, without a click event.
          onAuxClick={(event) => {
            // The middle button opens a tab; the right one only a menu.
            if (event.button === 1) markRead()
          }}
          className="min-w-0 flex-1 font-serif text-[18px] leading-snug font-semibold text-foreground decoration-accent/40 sm:text-[19px] underline-offset-4 hover:underline"
        >
          {item.headline}
        </Link>
        <OriginalLink url={item.url} title={item.headline} onOpen={markRead} />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted">
        <span className="font-medium text-foreground">{item.source_name}</span>
        {item.source_read_via && (
          <Chip tone="spark" title="Сайт блокирует бота. Читаем страницу в обход защиты">
            {item.source_read_via}
          </Chip>
        )}
        {item.ours && item.ours.length > 0 && (
          <Chip tone="ok" title="В записи упомянуты системы из вашего профиля">
            касается нас: {item.ours.join(', ')}
          </Chip>
        )}
        <span>{formatDate(item.published_at)}</span>
        <ReadingTime minutes={item.reading_minutes} />
        <PriorityChip item={item} />
        <VerifiedBadge item={item} />
        <ScoreBar score={item.score} />
        {item.interest_title && <Chip tone="neutral">{item.interest_title}</Chip>}
        {personal !== 0 && (
          <Chip
            tone={personal > 0 ? 'ok' : 'neutral'}
            title={`Поправка по вашим отметкам${item.personal_note ? `: ${item.personal_note}` : ''}`}
          >
            {personal > 0 ? '+' : ''}
            {personal.toFixed(2)} по вашим отметкам
          </Chip>
        )}
        <ReactionBar
          reactions={reactions ?? []}
          subject={item.headline}
          onReact={onReact}
          canHide={false}
          // Until the reader's reactions are loaded a click could not show them right.
          isDisabled={reactions === undefined}
          className="ml-auto"
        />
      </div>
      {translated && <p className="mt-1.5 text-xs text-muted">Оригинал: {item.title}</p>}
      {item.summary && (
        <p className="mt-2.5 text-sm leading-relaxed text-foreground/90">{item.summary}</p>
      )}
      <EntryDetails item={item} />
      {hasTimeline && <CveTimeline item={item} />}
      <IndicatorsBlock attack={item.attack} hidden={item.hidden_fields} />
      {item.why && (
        <p className="mt-2.5 border-l-2 border-warning pl-3 text-sm leading-relaxed text-muted">
          <span className="font-medium text-foreground">Почему это важно. </span>
          {item.why}
        </p>
      )}
      <StoryStack main={item.source_name} duplicates={item.duplicates} />
    </motion.article>
  )
}

type TopicSectionProps = {
  topic: Topic
  number: number
  digestId: string
  /** The place of the topic's first article in the whole digest, from 1. */
  firstPosition: number
  reactions: Record<string, ReactionKind[]> | undefined
  onReact: (articleId: number, kind: ReactionKind, isActive: boolean, position: number) => void
  hasTimeline: boolean
}

function TopicSection({
  topic,
  number,
  digestId,
  firstPosition,
  reactions,
  onReact,
  hasTimeline,
}: TopicSectionProps) {
  const { data: me } = useMe()
  const update = useUpdateSettings()
  const folded = me?.folded_sections ?? []
  const isKeptFolded = folded.includes(topic.title)
  // Opened for a moment by a jump to one of its entries, not for good.
  const [isRevealed, setRevealed] = useState(false)
  const [isAll, setAll] = useState(false)
  const [isNoteOpen, setNoteOpen] = useState(false)
  const isFolded = isKeptFolded && !isRevealed
  const lastPosition = firstPosition + topic.items.length - 1

  useEffect(() => {
    const onReveal = (event: Event) => {
      const wanted = (event as CustomEvent<number>).detail
      if (wanted < firstPosition || wanted > lastPosition) return
      setRevealed(true)
      setAll(true)
    }
    window.addEventListener(REVEAL_EVENT, onReveal)
    return () => window.removeEventListener(REVEAL_EVENT, onReveal)
  }, [firstPosition, lastPosition])

  const toggle = () => {
    setRevealed(false)
    // Kept with the account: the same section stays folded in the next issue too.
    update.mutate({ folded_sections: withFolded(folded, topic.title, !isFolded) })
  }
  const shown = firstEntries(topic.items, isAll)
  const hidden = topic.items.length - shown.length
  const summary = foldSummary(topic.items)

  return (
    <section>
      {/* A white card of its own, folded or open: on the dotted page a bare
          heading blended into the background. */}
      <div className="sticky top-14 z-10 py-1.5 md:top-0">
        <h3 className="rounded-2xl bg-surface shadow-surface">
          <button
            type="button"
            onClick={toggle}
            aria-expanded={!isFolded}
            title={
              isFolded
                ? 'Развернуть раздел'
                : 'Свернуть раздел, он останется свёрнутым и в следующих выпусках'
            }
            className="group flex w-full items-center gap-2.5 rounded-2xl px-4 py-2.5 text-left transition-colors hover:bg-surface-secondary/60"
          >
            <span className="tabular font-sans text-sm font-medium text-warning">
              {String(number).padStart(2, '0')}
            </span>
            {/* Stuck over the text on a phone, a heading of three lines would hide it. */}
            <span
              title={topic.title}
              className="min-w-0 truncate font-serif text-lg font-semibold tracking-tight md:overflow-visible md:text-xl md:whitespace-normal"
            >
              {topic.title}
            </span>
            <span className="tabular font-sans text-xs text-muted">{topic.items.length}</span>
            {isFolded && summary.high > 0 && <Chip tone="alarm">{summary.high} высокий</Chip>}
            {isFolded && summary.ours > 0 && <Chip tone="ok">касается нас: {summary.ours}</Chip>}
            <motion.span
              animate={{ rotate: isFolded ? -90 : 0 }}
              transition={{ duration: 0.2 }}
              className="ml-auto text-muted opacity-60 transition-opacity group-hover:opacity-100"
            >
              <ChevronDown size={18} />
            </motion.span>
          </button>
        </h3>
      </div>
      <AnimatePresence initial={false}>
        {!isFolded && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: EASE }}
            className="overflow-hidden"
          >
            {topic.overview && (
              <button
                type="button"
                onClick={() => setNoteOpen((value) => !value)}
                aria-expanded={isNoteOpen}
                className="mt-0.5 mb-1.5 flex w-full items-start gap-2 rounded-xl bg-surface px-4 py-2 text-left text-sm text-muted hover:text-foreground"
              >
                {/* Clamped inside the padding: no half of a second line peeks out below. */}
                <span className={clsx('min-w-0 flex-1', !isNoteOpen && 'line-clamp-1')}>
                  {topic.overview}
                </span>
                <ChevronDown
                  size={16}
                  aria-hidden
                  className={clsx(
                    'mt-0.5 shrink-0 transition-transform',
                    isNoteOpen && 'rotate-180',
                  )}
                />
              </button>
            )}
            <div className="space-y-1">
              {shown.map((item, index) => (
                <ItemCard
                  key={item.article_id}
                  item={item}
                  index={index}
                  placement={{ listId: digestId, position: firstPosition + index, slot: 'digest' }}
                  reactions={reactions ? (reactions[item.article_id] ?? []) : undefined}
                  onReact={(kind, isActive) =>
                    onReact(item.article_id, kind, isActive, firstPosition + index)
                  }
                  hasTimeline={hasTimeline}
                />
              ))}
            </div>
            {hidden > 0 && (
              <button
                type="button"
                onClick={() => setAll(true)}
                className="mt-2 mb-1 rounded-full bg-surface px-4 py-1.5 text-sm font-medium text-accent shadow-surface hover:underline"
              >
                Ещё {hidden} {plural(hidden, ['запись', 'записи', 'записей'])}
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function RejectedList({ items }: { items: DigestItem[] }) {
  const [open, setOpen] = useState(false)
  if (items.length === 0) return null
  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <span>
          <span className="text-sm font-semibold">Не вошло в выпуск</span>
          <span className="ml-2 text-xs text-muted">
            {items.length} {plural(items.length, ['кандидат', 'кандидата', 'кандидатов'])} с оценкой
            и причиной
          </span>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={18} className="text-muted" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="overflow-hidden"
          >
            <ul className="divide-y divide-separator border-t border-separator">
              {items.map((item) => (
                <li key={item.article_id} className="flex items-start gap-3 px-5 py-3">
                  <span className="tabular mt-0.5 w-9 shrink-0 text-xs font-semibold text-muted">
                    {item.score.toFixed(2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={articlePath(item.article_id)}
                      className="text-sm hover:text-accent-soft-foreground"
                    >
                      {item.title}
                    </Link>
                    <p className="mt-0.5 text-xs text-muted">
                      {item.source_name} · {formatDate(item.published_at)}
                      {item.reason && ` · ${item.reason}`}
                    </p>
                  </div>
                  <Chip tone={item.reject_reason === 'excluded' ? 'danger' : 'neutral'}>
                    {REJECT_LABELS[item.reject_reason ?? 'low_score'] ?? item.reject_reason}
                  </Chip>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

export function DigestView({ digest, previousId }: { digest: Digest; previousId?: string }) {
  // Interests whose weight or meaning the reader's marks had moved when this digest was built.
  const adapted = Object.values(digest.stats.adaptation ?? {}).filter(
    (item) => Math.abs(item.factor - 1) >= 0.01 || item.drift >= 0.005,
  ).length
  const stats = digest.stats
  const articleIds = digest.topics.flatMap((topic) => topic.items.map((item) => item.article_id))
  const reactions = useReactions(articleIds)
  const feedback = useFeedback()
  const react = (articleId: number, kind: ReactionKind, isActive: boolean, position: number) =>
    feedback.mutate({
      articleId,
      kind,
      isActive,
      context: 'digest',
      placement: { listId: digest.id, position, slot: 'digest' },
    })
  // A block the reader's profile hides is not drawn; the entries always are.
  const shows = (key: DigestBlockKey) => isShown(digest, key)
  // Articles are counted through the whole digest, topic after topic.
  const firstPositions = digest.topics.map(
    (_, index) =>
      1 + digest.topics.slice(0, index).reduce((count, topic) => count + topic.items.length, 0),
  )
  return (
    <div className="space-y-6">
      <Card className="p-6">
        {/* The title is in the header above, drawn from the history list. */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h2 className="sr-only">{digest.title ?? 'Дайджест'}</h2>
          <div className="flex flex-wrap gap-2">
            {previousId && (
              <Link
                to={`/compare?base=${previousId}&other=${digest.id}`}
                className={buttonClass('ghost', 'sm')}
              >
                <GitCompareArrows size={15} />
                Сравнить с предыдущим
              </Link>
            )}
            <a
              href={api.exportUrl(digest.id, 'md')}
              download
              className={buttonClass('secondary', 'sm')}
            >
              <FileText size={15} />
              Markdown
            </a>
            <a
              href={api.exportUrl(digest.id, 'docx')}
              download
              className={buttonClass('secondary', 'sm')}
            >
              <Download size={15} />
              DOCX
            </a>
            {digest.audience !== 'management' && shows('soc_export') && (
              <SocExport digestId={digest.id} />
            )}
            {shows('briefing') && <BriefingPlayer digest={digest} />}
            <MailButton digest={digest} />
          </div>
        </div>

        {digest.profile.audience === 'management' &&
          shows('implications') &&
          digest.implications.length > 0 && (
            <div className="mt-6">
              <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
                Что это значит для нас
              </h3>
              <ul className="mt-2 space-y-1.5">
                {digest.implications.map((point, index) => (
                  <motion.li
                    key={`${index}-${point}`}
                    {...rowMotion(index)}
                    className="flex gap-2.5 text-sm"
                  >
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
                    {point}
                  </motion.li>
                ))}
              </ul>
            </div>
          )}

        {digest.highlights.length > 0 && (
          <div className="mt-6">
            <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">Главное</h3>
            <ul className="mt-2 space-y-1.5">
              {digest.highlights.map((highlight, index) => (
                <motion.li
                  key={`${index}-${highlight}`}
                  {...rowMotion(index)}
                  className="flex gap-2.5 text-sm"
                >
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-warning" />
                  {highlight}
                </motion.li>
              ))}
            </ul>
          </div>
        )}

        {/* The numbers come after the news: what happened first, how it was found second. */}
        {(shows('funnel') || (shows('manual') && digest.manual)) && (
          <div className="mt-5 space-y-2">
            {shows('funnel') && <Funnel digest={digest} />}
            {shows('manual') && <ManualWork digest={digest} />}
          </div>
        )}

        {stats.degraded && (
          <p className="mt-4 flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
            <Info size={16} className="mt-0.5 shrink-0" />
            Модель была частично недоступна: оценила {stats.graded_by_model ?? 0} из{' '}
            {stats.candidates ?? 0} кандидатов и составила {stats.written_by_model ?? 0} из{' '}
            {stats.selected ?? 0} записей. Остальное обработал резервный алгоритм.
          </p>
        )}

        {shows('method') && (
          <p className="mt-4 text-xs text-muted">
            Поиск: {modelLabel(stats.embedding_model)}
            {stats.lexical_only && ' (только полнотекстовый)'} · оценка и тексты:{' '}
            {modelLabel(stats.llm)} · {stats.sources ?? 0}{' '}
            {plural(stats.sources ?? 0, ['источник', 'источника', 'источников'])}
            {stats.duplicates_merged ? ` · объединено повторов: ${stats.duplicates_merged}` : ''}
            {stats.personalized ? ` · поправок по вашим отметкам: ${stats.personalized}` : ''}
            {adapted > 0 ? ` · интересов подстроено под ваши отметки: ${adapted}` : ''}
            {stats.duration_seconds ? ` · ${Math.round(stats.duration_seconds)} с` : ''}
            {digest.finished_at && ` · ${formatDateTime(digest.finished_at)}`}
          </p>
        )}
      </Card>

      <IssueExtras digest={digest} />

      {digest.audience !== 'management' && shows('risk_matrix') && (
        <RiskMatrix
          entries={digest.topics.flatMap((topic, topicIndex) =>
            topic.items.map((item, index) => ({
              position: firstPositions[topicIndex] + index,
              item,
            })),
          )}
        />
      )}

      {/* Keyed by the digest: a voice picked for one must not carry over to the next. */}
      {digest.topics.length > 0 && shows('short') && (
        <ShortPanel key={digest.id} digestId={digest.id} />
      )}

      {digest.topics.length === 0 ? (
        <Card className="px-6 py-10 text-center text-sm text-muted">
          За этот период по выбранным интересам ничего не нашлось.
        </Card>
      ) : (
        <div className="space-y-7">
          {digest.topics.map((topic, index) => (
            <TopicSection
              key={topic.title}
              topic={topic}
              number={index + 1}
              digestId={digest.id}
              firstPosition={firstPositions[index]}
              reactions={reactions.data}
              onReact={react}
              hasTimeline={shows('cve_timeline')}
            />
          ))}
        </div>
      )}

      {shows('rejected') && <RejectedList items={digest.rejected} />}
      {/* Last, so that it stays docked at the bottom through the whole issue. */}
      {digest.topics.length > 0 && shows('ask') && (
        <AskDigest digestId={digest.id} audience={digest.audience ?? 'specialist'} />
      )}
    </div>
  )
}
