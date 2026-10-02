import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { Switch as SwitchPrimitive } from 'radix-ui'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  AutoAwesome,
  Block,
  ChevronDown,
  LibraryAdd,
  RotateCcw,
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
  dislikes: 'по тому, что вы отклонили',
}
// The weight factor runs 0.9..1.1; the bar shows it around the middle.
const FACTOR_SPAN = 0.1

/** Marks are weighed (a save counts 1.2, an old like less than a fresh one): one decimal at most. */
function amount(value: number): string {
  return (Math.round(value * 10) / 10).toLocaleString('ru-RU')
}

function M3Switch({
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
    <SwitchPrimitive.Root
      checked={checked}
      onCheckedChange={(value) => !isBusy && onChange(value)}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      aria-busy={isBusy || undefined}
      className="relative inline-flex h-8 w-[52px] shrink-0 items-center rounded-full border-2 border-outline bg-surface-container-highest transition-colors duration-200 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary"
    >
      <SwitchPrimitive.Thumb className="block size-4 translate-x-1.5 rounded-full bg-outline transition-[translate,width,height,background-color] duration-200 ease-[cubic-bezier(0.2,0,0,1)] data-[state=checked]:size-6 data-[state=checked]:translate-x-[22px] data-[state=checked]:bg-primary-foreground" />
    </SwitchPrimitive.Root>
  )
}

function FactorBar({ factor }: { factor: number }) {
  const offset = Math.max(-1, Math.min(1, (factor - 1) / FACTOR_SPAN))
  return (
    <span
      aria-hidden
      className="relative hidden h-1.5 w-20 rounded-full bg-surface-container-highest sm:block"
    >
      <span className="absolute inset-y-0 left-1/2 w-px bg-outline" />
      <motion.span
        className={clsx(
          'absolute inset-y-0 rounded-full',
          offset >= 0 ? 'left-1/2 bg-primary' : 'right-1/2 bg-spark',
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
    item.skipped > 0 && `пролистано ${item.skipped}`,
  ].filter(Boolean)
  const Trend = item.weight >= item.stated_weight ? TrendingUp : TrendingDown
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-2.5">
      <span className="truncate text-sm font-medium" title={item.title}>
        {item.title}
      </span>
      <span className="flex items-center gap-2 text-xs tabular-nums">
        <FactorBar factor={item.factor} />
        <span className={clsx(moved ? 'text-foreground' : 'text-muted-foreground')}>
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
            className={item.weight >= item.stated_weight ? 'text-primary' : 'text-spark'}
          />
        )}
      </span>
      <span className="col-span-2 text-xs text-muted-foreground">
        {marks.length > 0 ? marks.join(' · ') : 'отметок пока нет'}
        {item.drift >= 0.005 &&
          ` · смысл сдвинут к понравившемуся на ${Math.round(item.drift * 100)}%`}
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
      className="overflow-hidden rounded-2xl bg-surface-container px-4 py-3.5"
    >
      <p className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant">
        <Kind size={15} className={isExclusion ? 'text-spark' : 'text-primary'} />
        {isExclusion ? 'Не показывать' : 'Новая тема'} · {SOURCE[suggestion.source]}
      </p>
      <p className="mt-1.5 font-semibold break-words">{suggestion.title}</p>
      {isExclusion ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Статьи с этим словом перестанут попадать в ленту и выпуски этого профиля.
        </p>
      ) : (
        suggestion.description && (
          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
            {suggestion.description}
          </p>
        )
      )}
      {!isExclusion && suggestion.keywords.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {suggestion.keywords.map((keyword) => (
            <li
              key={keyword}
              className="rounded-lg bg-secondary-container px-2 py-0.5 text-xs break-words text-on-secondary-container"
            >
              {keyword}
            </li>
          ))}
        </ul>
      )}
      {suggestion.articles.length > 0 && (
        <ul className="mt-2.5 space-y-1 border-l-2 border-outline-variant pl-3">
          {suggestion.articles.map((article) => (
            <li key={article.id} className="text-xs">
              <a
                href={externalHref(article.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="line-clamp-1 text-foreground hover:text-primary hover:underline"
              >
                {article.title}
              </a>
              <span className="text-muted-foreground">{article.source_name}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button
          size="sm"
          variant="ghost"
          disabled={isBusy || isLocked}
          aria-label={`Не нужно: «${suggestion.title}»`}
          onClick={() => onDecide(false)}
        >
          Не нужно
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
      className="rounded-3xl border border-outline-variant bg-surface-container-low p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-primary-container text-on-primary-container">
          <AutoAwesome size={22} filled={isOn} />
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="adaptation-title"
            ref={heading}
            tabIndex={-1}
            className="font-semibold outline-none"
          >
            Подстраивается под вас
          </h2>
          <p id="adaptation-summary" className="mt-0.5 text-sm text-muted-foreground">
            {!isOn
              ? 'Выключено: лента и выпуски берут профиль таким, как он записан.'
              : hasLearned && marks
                ? `Отметки по темам профиля: «больше такого» ${amount(marks.positives)}, «меньше такого» ${amount(marks.negatives)}, пролистано ${marks.skipped}${data?.updated_at ? ` · пересчитано ${formatRelative(data.updated_at)}` : ''}`
                : 'Отмечайте «больше такого» и «меньше такого» в ленте и выпусках: веса интересов и их смысл подстроятся, а новые темы появятся здесь предложениями.'}
          </p>
        </div>
        <M3Switch
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
            className="flex w-full items-center gap-1.5 rounded-lg py-1 text-sm font-medium text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
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
                <ul className="divide-y divide-outline-variant">
                  {data.interests.map((item) => (
                    <InterestRow key={item.interest_id} item={item} />
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">
                  Вес интереса растёт, когда то, что он приносит, вам нравится, и падает, когда вы
                  это отклоняете, но не больше чем на десятую часть. Смысл интереса сдвигается к
                  статьям, которые вам понравились. Записанный профиль при этом не меняется.
                </p>
                <div className="mt-3 flex justify-end">
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<RotateCcw size={14} />}
                    isBusy={reset.isPending}
                    onClick={() => {
                      if (window.confirm('Забыть всё, чему профиль научился по вашим отметкам?')) {
                        reset.mutate(profile.id)
                      }
                    }}
                  >
                    Начать заново
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
