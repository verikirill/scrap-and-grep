import clsx from 'clsx'
import {
  ChevronDown,
  Download,
  FileText,
  GitCompareArrows,
  Info,
} from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router'
import { buttonClass, EASE, rowMotion } from '../../components/tokens'
import { AnimatedNumber, Card, Chip, ScoreBar, ReadingTime } from '../../components/ui'
import { api } from '../../lib/api'
import type { Digest, DigestItem, Placement, ReactionKind, Topic } from '../../lib/api'
import {
  formatDate,
  formatDateTime,
  modelLabel,
  plural,
  REJECT_LABELS,
} from '../../lib/format'
import { useSeen } from '../../lib/impressions'
import { useFeedback, useReactions } from '../../lib/queries'
import { ReactionBar } from '../feed/ReactionBar'
import { OriginalLink } from '../reader/OriginalLink'
import { articlePath } from '../reader/paths'
import { BriefingPlayer } from './BriefingPlayer'
import { EntryDetails, PriorityChip } from './EntryCard'
import { MailButton } from './MailButton'
import { IssueExtras, ManualWork } from './IssueExtras'
import { ShortPanel } from './ShortPanel'
import { StoryStack } from './StoryStack'
import { IndicatorsBlock, SocExport } from './ThreatIntel'

function Funnel({ digest }: { digest: Digest }) {
  const stats = digest.stats
  const steps = [
    { label: 'публикаций за период', value: stats.window_total ?? 0 },
    { label: 'кандидатов по интересам', value: stats.candidates ?? 0 },
    { label: 'в выпуске', value: stats.selected ?? 0 },
  ]
  const max = Math.max(steps[0].value, 1)
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {steps.map((step, index) => (
        <div key={step.label} className="rounded-xl bg-surface-secondary px-4 py-3">
          <AnimatedNumber value={step.value} className="text-2xl font-semibold" />
          <p className="text-xs text-muted">{step.label}</p>
          <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-separator">
            <motion.div
              className={clsx(
                'h-full origin-left rounded-full',
                index === 2 ? 'bg-warning' : 'bg-accent',
              )}
              initial={{ scaleX: 0 }}
              // A log scale keeps the last bar visible: 20 of 800 would be a sliver.
              animate={{ scaleX: Math.log1p(step.value) / Math.log1p(max) }}
              transition={{ duration: 0.8, ease: EASE, delay: 0.1 * index }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

type ItemCardProps = {
  item: DigestItem
  index: number
  placement: Placement
  reactions: ReactionKind[] | undefined
  onReact: (kind: ReactionKind, isActive: boolean) => void
}

function ItemCard({ item, index, placement, reactions, onReact }: ItemCardProps) {
  const translated = item.headline !== item.title
  const personal = Math.abs(item.personal) >= 0.005 ? item.personal : 0
  const seenRef = useSeen(item.article_id, 'digest', !reactions?.length, placement)
  const markRead = () => {
    if (reactions !== undefined && !reactions.includes('open')) onReact('open', true)
  }
  return (
    <motion.article
      ref={seenRef}
      {...rowMotion(index)}
      className="group rounded-xl border border-transparent px-4 py-4 transition-colors duration-200 hover:border-separator hover:bg-surface"
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
      {item.summary && <p className="mt-2.5 text-sm text-foreground/90">{item.summary}</p>}
      <EntryDetails item={item} />
      <IndicatorsBlock attack={item.attack} />
      {item.why && (
        <p className="mt-2.5 border-l-2 border-warning pl-3 text-sm text-muted">
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
}

function TopicSection({
  topic,
  number,
  digestId,
  firstPosition,
  reactions,
  onReact,
}: TopicSectionProps) {
  return (
    <section>
      <div className="sticky top-14 z-10 -mx-1 bg-background/90 px-1 py-2 backdrop-blur md:top-0">
        <h3 className="flex items-baseline gap-2.5 font-serif text-lg font-semibold tracking-tight md:text-xl">
          <span className="tabular font-sans text-sm font-medium text-warning">
            {String(number).padStart(2, '0')}
          </span>
          {/* Stuck over the text on a phone, a heading of three lines would hide it. */}
          <span
            title={topic.title}
            className="min-w-0 truncate md:overflow-visible md:whitespace-normal"
          >
            {topic.title}
          </span>
          <span className="tabular font-sans text-xs font-normal text-muted">
            {topic.items.length}
          </span>
        </h3>
      </div>
      {topic.overview && <p className="mt-1 mb-2 px-4 text-sm text-muted">{topic.overview}</p>}
      <div className="space-y-1">
        {topic.items.map((item, index) => (
          <ItemCard
            key={item.article_id}
            item={item}
            index={index}
            placement={{ listId: digestId, position: firstPosition + index, slot: 'digest' }}
            reactions={reactions ? (reactions[item.article_id] ?? []) : undefined}
            onReact={(kind, isActive) =>
              onReact(item.article_id, kind, isActive, firstPosition + index)
            }
          />
        ))}
      </div>
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
            {digest.audience !== 'management' && <SocExport digestId={digest.id} />}
            <BriefingPlayer digest={digest} />
            <MailButton digest={digest} />
          </div>
        </div>

        <div className="mt-5">
          <Funnel digest={digest} />
          <ManualWork digest={digest} />
        </div>

        {stats.degraded && (
          <p className="mt-4 flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
            <Info size={16} className="mt-0.5 shrink-0" />
            Модель была частично недоступна: оценила {stats.graded_by_model ?? 0} из{' '}
            {stats.candidates ?? 0} кандидатов и составила {stats.written_by_model ?? 0} из{' '}
            {stats.selected ?? 0} записей. Остальное обработал резервный алгоритм.
          </p>
        )}

        {digest.profile.audience === 'management' && digest.implications.length > 0 && (
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

        <p className="mt-5 text-xs text-muted">
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
      </Card>

      <IssueExtras digest={digest} />

      {/* Keyed by the digest: a voice picked for one must not carry over to the next. */}
      {digest.topics.length > 0 && <ShortPanel key={digest.id} digestId={digest.id} />}

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
            />
          ))}
        </div>
      )}

      <RejectedList items={digest.rejected} />
    </div>
  )
}
