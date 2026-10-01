import clsx from 'clsx'
import { format, subDays } from 'date-fns'
import { ru } from 'date-fns/locale'
import { AnimatePresence, LayoutGroup, motion } from 'motion/react'
import { Suspense, lazy, useState } from 'react'
import type { DateRange } from 'react-day-picker'
import { Link } from 'react-router'
import { CalendarMonth, CircleCheck, Newspaper } from '../../components/icons'
import { Segmented } from '../../components/Segmented'
import { useRadioKeys } from '../../components/useRadioKeys'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { buttonClass } from '../../components/tokens'
import { Button, Card, ErrorNote, Spinner } from '../../components/ui'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover'
import type { DigestPeriod, Profile } from '../../lib/api'
import { plural } from '../../lib/format'
import { useCreateDigest } from '../../lib/queries'

const PERIODS = [
  { value: '1', label: 'Сутки' },
  { value: '3', label: '3 дня' },
  { value: '7', label: 'Неделя' },
  { value: '14', label: '2 недели', short: '2 нед.' },
  { value: '30', label: 'Месяц' },
] as const
type PeriodValue = (typeof PERIODS)[number]['value'] | 'custom'
// The backend keeps publications for this long; older dates hold nothing.
const MAX_DAYS_BACK = 90
const SPRING = { type: 'spring', stiffness: 380, damping: 32 } as const
// The date picker brings react-day-picker along: it loads when it is opened.
const Calendar = lazy(() =>
  import('../../components/ui/calendar').then((module) => ({ default: module.Calendar })),
)

type Props = {
  profiles: Profile[]
  initialProfileId?: string | null
  onCreated: (digestId: string) => void
}

function rangeLabel(range: DateRange | undefined): string {
  if (!range?.from) return 'Даты'
  const from = format(range.from, 'd MMM', { locale: ru })
  if (!range.to || range.to.getTime() === range.from.getTime()) return from
  return `${from} - ${format(range.to, 'd MMM', { locale: ru })}`
}

/** The whole of the last day of a range: a digest "to 20 September" includes the 20th. */
function periodOf(
  value: PeriodValue,
  range: DateRange | undefined,
  now: Date,
): DigestPeriod | null {
  if (value !== 'custom') return { days: Number(value) }
  if (!range?.from) return null
  const end = new Date(range.to ?? range.from)
  end.setHours(23, 59, 59, 999)
  const start = new Date(range.from)
  start.setHours(0, 0, 0, 0)
  return { start, end: end > now ? now : end }
}

export function BuildPanel({ profiles, initialProfileId, onCreated }: Props) {
  const [profileId, setProfileId] = useState<string | null>(null)
  const [period, setPeriod] = useState<PeriodValue>('7')
  const [range, setRange] = useState<DateRange | undefined>()
  const [isPicking, setPicking] = useState(false)
  // The calendar's limits: stable between renders, renewed whenever it opens.
  const [today, setToday] = useState(() => new Date())
  const create = useCreateDigest()

  // An explicit click wins; otherwise the profile from the URL, then the first one.
  const fromUrl = profiles.some((profile) => profile.id === initialProfileId)
    ? initialProfileId
    : null
  const selectedId = profileId ?? fromUrl ?? profiles[0]?.id ?? null
  const chosen = periodOf(period, range, today)
  const profileKeys = useRadioKeys(
    profiles.length,
    profiles.findIndex((profile) => profile.id === selectedId),
    (index) => setProfileId(profiles[index].id),
  )

  const submit = () => {
    // A range ending today ends now, at the press, not when the panel opened.
    const pressed = periodOf(period, range, new Date())
    if (!selectedId || !pressed) return
    // Pin the choice: after the build the URL no longer carries ?profile=.
    setProfileId(selectedId)
    create.mutate(
      { profileId: selectedId, period: pressed },
      { onSuccess: (digest) => onCreated(digest.id) },
    )
  }

  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-medium">Для кого выпуск</h2>
        <Link to="/profiles" className={buttonClass('ghost', 'sm')}>
          Настроить интересы
        </Link>
      </div>

      <LayoutGroup id="build-profiles">
        <div
          className="grid grid-cols-[minmax(0,1fr)] gap-2.5 sm:grid-cols-2 xl:grid-cols-3"
          role="radiogroup"
          aria-label="Профиль читателя"
          onKeyDown={profileKeys.onKeyDown}
        >
          {profiles.map((profile, index) => {
            const isActive = profile.id === selectedId
            const count = profile.spec.interests.length
            return (
              <button
                key={profile.id}
                type="button"
                role="radio"
                {...profileKeys.itemProps(index)}
                onClick={() => setProfileId(profile.id)}
                aria-checked={isActive}
                className={clsx(
                  'group relative isolate flex items-start gap-3 rounded-2xl p-3.5 text-left transition-colors duration-300',
                  isActive
                    ? 'text-on-primary-container'
                    : 'bg-surface-container-low text-on-surface ring-1 ring-outline-variant ring-inset hover:bg-surface-container',
                )}
              >
                {/* One highlight for the group: it flows from card to card. */}
                {isActive && (
                  <motion.span
                    layoutId="profile-highlight"
                    className="absolute inset-0 -z-10 bg-primary-container ring-2 ring-primary ring-inset"
                    style={{ borderRadius: 16 }}
                    transition={SPRING}
                  />
                )}
                <ProfileAvatar profile={profile} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{profile.spec.name}</span>
                  <span
                    className={clsx(
                      'mt-0.5 block text-xs',
                      isActive ? 'opacity-80' : 'text-on-surface-variant',
                    )}
                  >
                    {count} {plural(count, ['интерес', 'интереса', 'интересов'])} · до{' '}
                    {profile.spec.max_items} публикаций
                  </span>
                </span>
                <AnimatePresence initial={false}>
                  {isActive && (
                    <motion.span
                      initial={{ scale: 0.4, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.4, opacity: 0 }}
                      transition={SPRING}
                      className="text-primary"
                    >
                      <CircleCheck size={22} filled />
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            )
          })}
        </div>
      </LayoutGroup>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Segmented
          label="Период"
          value={period}
          onChange={(value) => setPeriod(value)}
          options={PERIODS}
          className="w-full sm:w-auto sm:shrink-0"
        />
        <Popover
          open={isPicking}
          onOpenChange={(open) => {
            if (open) setToday(new Date())
            setPicking(open)
          }}
        >
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-pressed={period === 'custom'}
              className={clsx(
                'state-layer relative inline-flex h-11 items-center gap-2 overflow-hidden rounded-full border px-4 text-[13px] transition-colors duration-300',
                period === 'custom'
                  ? 'border-transparent bg-primary font-semibold text-primary-foreground shadow-elevation-1'
                  : 'border-outline-variant font-medium text-on-surface-variant hover:text-on-surface',
              )}
            >
              <CalendarMonth size={18} filled={period === 'custom'} />
              {period === 'custom' ? rangeLabel(range) : 'Свои даты'}
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-auto rounded-3xl p-2">
            <Suspense
              fallback={
                <div className="grid h-72 w-64 place-items-center">
                  <Spinner className="size-6 text-primary" label="Открываем календарь" />
                </div>
              }
            >
              <Calendar
                mode="range"
                locale={ru}
                numberOfMonths={1}
                selected={range}
                defaultMonth={range?.from ?? today}
                disabled={{ before: subDays(today, MAX_DAYS_BACK), after: today }}
                onSelect={(next) => {
                  setRange(next)
                  if (next?.from) setPeriod('custom')
                  if (next?.from && next.to && next.to.getTime() !== next.from.getTime()) {
                    setPicking(false)
                  }
                }}
              />
            </Suspense>
          </PopoverContent>
        </Popover>

        <Button
          variant="primary"
          icon={<Newspaper size={18} />}
          isBusy={create.isPending}
          disabled={!selectedId || !chosen}
          onClick={submit}
          className="ml-auto"
        >
          Собрать дайджест
        </Button>
      </div>
      {create.error && (
        <div className="mt-3">
          <ErrorNote error={create.error} />
        </div>
      )}
    </Card>
  )
}
