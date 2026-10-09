import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { Switch } from '@heroui/react'
import { useRef, useState } from 'react'
import { toast } from '../../lib/toast'
import {
  Block,
  ChevronDown,
  LibraryAdd,
  RotateCcw,
  SlidersHorizontal,
  TrendingDown,
  TrendingUp,
  Users,
} from '../../components/icons'
import { EASE } from '../../components/tokens'
import { Button, ErrorNote } from '../../components/ui'
import type { InterestLearning, Profile, Suggestion } from '../../lib/api'
import { externalHref, formatRelative } from '../../lib/format'
import {
  useAdaptation,
  useDecideSuggestion,
  useResetAdaptation,
  useSetAdaptive,
} from '../../lib/queries'

const SOURCE: Record<Suggestion['source'], string> = {
  likes: 'по вашим отметкам',
  similar_readers: 'читают коллеги с похожими интересами',
  dislikes: 'по скрытым публикациям',
}
// The weight factor runs 0.9..1.1; the bar shows it around the middle.
const FACTOR_SPAN = 0.1

/** Marks are weighed (a save counts 1.2, an old like less than a fresh one): one decimal at most. */
function amount(value: number): string {
  return (Math.round(value * 10) / 10).toLocaleString('ru-RU')
}

function SettingSwitch({
  checked,
  onChange,
  labelledBy,
  describedBy,
  isBusy,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  labelledBy: string
  describedBy: string
  isBusy?: boolean
}) {
  return (
    // Never disabled: a disabled control drops the keyboard focus. A click
    // while the last one is on its way is ignored instead.
    <Switch
      isSelected={checked}
      onChange={(value) => !isBusy && onChange(value)}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      aria-busy={isBusy || undefined}
    >
      <Switch.Control>
        <Switch.Thumb />
      </Switch.Control>
    </Switch>
  )
}

function FactorBar({ factor }: { factor: number }) {
  const offset = Math.max(-1, Math.min(1, (factor - 1) / FACTOR_SPAN))
  return (
    <span aria-hidden className="relative hidden h-1.5 w-20 rounded-full bg-default sm:block">
      <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
      <motion.span
        className={clsx(
          'absolute inset-y-0 rounded-full',
          offset >= 0 ? 'left-1/2 bg-accent' : 'right-1/2 bg-warning',
        )}
        initial={{ width: 0 }}
        animate={{ width: `${Math.abs(offset) * 50}%` }}
        transition={{ duration: 0.5, ease: EASE }}
      />
    </span>
  )
}

function InterestRow({ item }: { item: InterestLearning }) {
  const moved = Math.abs(item.weight - item.stated_weight) >= 0.01
  const marks = [
    item.positives > 0 && `«больше такого» ${amount(item.positives)}`,
    item.negatives > 0 && `«меньше такого» ${amount(item.negatives)}`,
    item.skipped > 0 && `пропущено ${item.skipped}`,
  ].filter(Boolean)
  const Trend = item.weight >= item.stated_weight ? TrendingUp : TrendingDown
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-2.5">
      <span className="truncate text-sm font-medium" title={item.title}>
        {item.title}
      </span>
      <span className="flex items-center gap-2 text-xs tabular-nums">
        <FactorBar factor={item.factor} />
        <span className={clsx(moved ? 'text-foreground' : 'text-muted')}>
          {item.stated_weight.toFixed(2)}
          {moved && (
            <>
              {' → '}
              <span className="font-semibold">{item.weight.toFixed(2)}</span>
            </>
          )}
        </span>
        {moved && (
          <Trend
            size={14}
            className={item.weight >= item.stated_weight ? 'text-accent' : 'text-warning'}
          />
        )}
      </span>
      <span className="col-span-2 text-xs text-muted">
        {marks.length > 0 ? marks.join(' · ') : 'отметок пока нет'}
        {item.drift >= 0.005 &&
          `· фокус сдвинут к понравившемуся на ${Math.round(item.drift * 100)}%`}
      </span>
    </li>
  )
}

function SuggestionCard({
  suggestion,
  isBusy,
  isLocked,
  onDecide,
}: {
  suggestion: Suggestion
  isBusy: boolean
  // Another card is being decided: one decision at a time.
  isLocked: boolean
  onDecide: (isAccepted: boolean) => void
}) {
  const isExclusion = suggestion.kind === 'exclusion'
  const Kind = isExclusion ? Block : suggestion.source === 'similar_readers' ? Users : LibraryAdd
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, paddingTop: 0, paddingBottom: 0, pointerEvents: 'none' }}
      transition={{ duration: 0.3, ease: EASE }}
      className="overflow-hidden rounded-2xl bg-surface-secondary px-4 py-3.5"
    >
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
        <Kind size={15} className={isExclusion ? 'text-warning' : 'text-accent'} />
        {isExclusion ? 'Не показывать' : 'Новая тема'} · {SOURCE[suggestion.source]}
      </p>
      <p className="mt-1.5 font-semibold break-words">{suggestion.title}</p>
      {isExclusion ? (
        <p className="mt-1 text-sm text-muted">
          Публикации с этим словом не попадут в ленту и выпуски по этому профилю.
        </p>
      ) : (
        suggestion.description && (
          <p className="mt-1 line-clamp-2 text-sm text-muted">{suggestion.description}</p>
        )
      )}
      {!isExclusion && suggestion.keywords.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {suggestion.keywords.map((keyword) => (
            <li
              key={keyword}
              className="rounded-lg bg-default px-2 py-0.5 text-xs break-words text-default-foreground"
            >
              {keyword}
            </li>
          ))}
        </ul>
      )}
      {suggestion.articles.length > 0 && (
        <ul className="mt-2.5 space-y-1 border-l-2 border-separator pl-3">
          {suggestion.articles.map((article) => (
            <li key={article.id} className="text-xs">
              <a
                href={externalHref(article.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="line-clamp-1 text-foreground hover:text-accent hover:underline"
              >
                {article.title}
              </a>
              <span className="text-muted">{article.source_name}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button
          size="sm"
          variant="ghost"
          disabled={isBusy || isLocked}
          aria-label={`Отклонить: «${suggestion.title}»`}
          onClick={() => onDecide(false)}
        >
          Отклонить
        </Button>
        <Button
          size="sm"
          variant="tonal"
          isBusy={isBusy}
          disabled={isLocked}
          aria-label={
            isExclusion
              ? `Исключить «${suggestion.title}»`
              : `Добавить тему «${suggestion.title}» в профиль`
          }
          onClick={() => onDecide(true)}
        >
          {isExclusion ? 'Исключить' : 'Добавить в профиль'}
        </Button>
      </div>
    </motion.li>
  )
}

/**
 * How the profile follows its reader: on or off, what each interest learned,
 * and the changes the marks point at. Accepting one edits the profile, and
 * the editor's draft takes the same change through `onApplied`.
 */
export function AdaptationPanel({
  profile,
  onApplied,
}: {
  profile: Profile
  onApplied: (profile: Profile) => void
}) {
  const adaptation = useAdaptation(profile.id)
  const setAdaptive = useSetAdaptive()
  const reset = useResetAdaptation()
  const decide = useDecideSuggestion()
  const [isDetailsOpen, setIsDetailsOpen] = useState(false)
  // After a card leaves, the focus goes back to the panel, not to the page.
  const heading = useRef<HTMLHeadingElement>(null)
  const data = adaptation.data
  const isOn = data?.adaptive ?? profile.adaptive
  const marks = data?.interests.reduce(
    (sum, item) => ({
      positives: sum.positives + item.positives,
      negatives: sum.negatives + item.negatives,
      skipped: sum.skipped + item.skipped,
    }),
    { positives: 0, negatives: 0, skipped: 0 },
  )
  const hasLearned = Boolean(marks && marks.positives + marks.negatives + marks.skipped > 0)

  return (
    <section
      aria-labelledby="adaptation-title"
      className="rounded-3xl border border-separator bg-background p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent-soft-foreground">
          <SlidersHorizontal size={22} filled={isOn} />
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="adaptation-title"
            ref={heading}
            tabIndex={-1}
            className="font-semibold outline-none"
          >
            Подстройка по отметкам
          </h2>
          <p id="adaptation-summary" className="mt-0.5 text-sm text-muted">
            {!isOn
              ? 'Выключено. Лента и выпуски используют профиль без изменений.'
              : hasLearned && marks
                ? `Отметки по темам профиля: «больше такого» ${amount(marks.positives)}, «меньше такого» ${amount(marks.negatives)}, пролистано ${marks.skipped}${data?.updated_at ? ` · пересчитано ${formatRelative(data.updated_at)}` : ''}`
                : 'Отмечайте публикации в ленте и выпусках, и сервис подстроит веса интересов, а новые темы предложит здесь.'}
          </p>
        </div>
        <SettingSwitch
          checked={isOn}
          labelledBy="adaptation-title"
          describedBy="adaptation-summary"
          isBusy={setAdaptive.isPending}
          onChange={(adaptive) => setAdaptive.mutate({ profileId: profile.id, adaptive })}
        />
      </div>

      <div className="mt-3 space-y-2">
        <ErrorNote error={adaptation.error ?? setAdaptive.error ?? reset.error ?? decide.error} />
      </div>

      {isOn && data && data.suggestions.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2.5" aria-label="Предложения для профиля">
          <AnimatePresence initial={false}>
            {data.suggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                isBusy={decide.isPending && decide.variables?.suggestionId === suggestion.id}
                isLocked={decide.isPending && decide.variables?.suggestionId !== suggestion.id}
                onDecide={(isAccepted) =>
                  decide.mutate(
                    { profileId: profile.id, suggestionId: suggestion.id, isAccepted },
                    {
                      onSuccess: (changed) => {
                        heading.current?.focus()
                        if (!changed) return
                        onApplied(changed)
                        toast.success(
                          suggestion.kind === 'exclusion'
                            ? `«${suggestion.title}» больше не покажем`
                            : `Тема «${suggestion.title}» добавлена в профиль`,
                        )
                      },
                    },
                  )
                }
              />
            ))}
          </AnimatePresence>
        </ul>
      )}

      {isOn && hasLearned && data && (
        <div className="mt-4">
          <button
            type="button"
            aria-expanded={isDetailsOpen}
            aria-controls="adaptation-details"
            onClick={() => setIsDetailsOpen((open) => !open)}
            className="flex w-full items-center gap-1.5 rounded-lg py-1 text-sm font-medium text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Как подстроены интересы
            <ChevronDown
              aria-hidden
              size={18}
              className={clsx('transition-transform duration-300', isDetailsOpen && 'rotate-180')}
            />
          </button>
          <AnimatePresence initial={false}>
            {isDetailsOpen && (
              <motion.div
                id="adaptation-details"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: EASE }}
                className="overflow-hidden"
              >
                <ul className="divide-y divide-separator">
                  {data.interests.map((item) => (
                    <InterestRow key={item.interest_id} item={item} />
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted">
                  Вес интереса растёт от положительных отметок и снижается от отрицательных (не
                  больше чем на 10%). Фокус подстраивается под понравившиеся статьи, а сохранённый
                  профиль не меняется.
                </p>
                <div className="mt-3 flex justify-end">
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<RotateCcw size={14} />}
                    isBusy={reset.isPending}
                    onClick={() => {
                      if (
                        window.confirm('Сбросить результаты адаптации профиля по вашим отметкам?')
                      ) {
                        reset.mutate(profile.id)
                      }
                    }}
                  >
                    Сбросить обучение
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </section>
  )
}
