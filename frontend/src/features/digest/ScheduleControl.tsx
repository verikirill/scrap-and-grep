import clsx from 'clsx'
import { useState } from 'react'
import { cn } from '../../lib/utils'
import { toast } from 'sonner'
import { EventRepeat } from '../../components/icons'
import { Segmented } from '../../components/Segmented'
import { INPUT_CLASS } from '../../components/tokens'
import { Button, ErrorNote } from '../../components/ui'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover'
import { useRadioKeys } from '../../components/useRadioKeys'
import type { Cadence, DigestSchedule, Profile, ScheduleInput } from '../../lib/api'
import { useSchedule } from '../../lib/queries'
import { scheduleLabel } from '../../lib/schedule'

const CADENCES = [
  { value: 'daily', label: 'Каждый день' },
  { value: 'weekdays', label: 'По будням' },
  { value: 'weekly', label: 'Раз в неделю' },
] as const satisfies readonly { value: Cadence; label: string }[]
const DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const DAY_NAMES = [
  'понедельник',
  'вторник',
  'среда',
  'четверг',
  'пятница',
  'суббота',
  'воскресенье',
]
const DEFAULT: Omit<ScheduleInput, 'timezone'> = { cadence: 'weekdays', weekday: 0, time: '09:00' }

function browserZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

/** The next run in the schedule's own zone: the same clock as its time of day. */
function nextLabel(iso: string, timeZone: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function WeekdayPicker({ value, onChange }: { value: number; onChange: (day: number) => void }) {
  const keys = useRadioKeys(DAYS.length, value, onChange)
  return (
    <div
      role="radiogroup"
      aria-label="День недели"
      className="grid grid-cols-7 gap-1"
      onKeyDown={keys.onKeyDown}
    >
      {DAYS.map((day, index) => (
        <button
          key={day}
          type="button"
          role="radio"
          {...keys.itemProps(index)}
          aria-checked={value === index}
          // The visible abbreviation first: speech input says what it sees.
          aria-label={`${day}, ${DAY_NAMES[index]}`}
          onClick={() => onChange(index)}
          className={clsx(
            'h-9 rounded-full text-xs font-medium transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-primary',
            value === index
              ? 'bg-primary text-primary-foreground'
              : 'text-on-surface-variant hover:bg-surface-container-high',
          )}
        >
          {day}
        </button>
      ))}
    </div>
  )
}

/**
 * The digest of a profile built by itself: when, and when next. The time is
 * the reader's own: the browser's time zone goes with the schedule.
 */
export function ScheduleControl({
  profile,
  schedule,
}: {
  profile: Profile
  schedule: DigestSchedule | null
}) {
  const { save, remove } = useSchedule()
  const [isOpen, setOpen] = useState(false)
  const [draft, setDraft] = useState<Omit<ScheduleInput, 'timezone'>>(DEFAULT)
  // A schedule keeps its zone: saving it from another place does not move it.
  const zone = schedule?.timezone ?? browserZone()

  const open = (next: boolean) => {
    if (next) {
      // Every opening starts from what is saved, not from an abandoned edit.
      setDraft(
        schedule
          ? { cadence: schedule.cadence, weekday: schedule.weekday ?? 0, time: schedule.time }
          : DEFAULT,
      )
      save.reset()
      remove.reset()
    }
    setOpen(next)
  }

  const submit = () =>
    save.mutate(
      {
        profileId: profile.id,
        schedule: {
          ...draft,
          weekday: draft.cadence === 'weekly' ? draft.weekday : null,
          timezone: zone,
        },
      },
      {
        onSuccess: (saved) => {
          setOpen(false)
          toast.success(
            `Следующий выпуск соберётся ${nextLabel(saved.next_run_at, saved.timezone)}`,
          )
        },
      },
    )

  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl bg-surface-container px-4 py-2.5">
      <EventRepeat
        size={20}
        filled={Boolean(schedule)}
        className={schedule ? 'text-primary' : 'text-on-surface-variant'}
      />
      <p className="min-w-0 flex-1 text-sm">
        {schedule ? (
          <>
            <span className="font-medium">Собирается сам {scheduleLabel(schedule)}</span>
            <span className="text-muted-foreground">
              {' '}
              · следующий {nextLabel(schedule.next_run_at, schedule.timezone)}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground">
            Выпуск этого профиля может собираться сам, по расписанию
          </span>
        )}
      </p>
      <Popover open={isOpen} onOpenChange={open}>
        <PopoverTrigger asChild>
          <Button size="sm" variant={schedule ? 'ghost' : 'tonal'}>
            {schedule ? 'Изменить' : 'Настроить'}
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          collisionPadding={12}
          className="w-[min(22rem,calc(100vw-2rem))] space-y-4 rounded-3xl p-4"
        >
          <p className="font-medium break-words">Собирать «{profile.spec.name}» самому</p>
          <Segmented
            label="Как часто"
            value={draft.cadence}
            onChange={(cadence) => setDraft((current) => ({ ...current, cadence }))}
            options={CADENCES}
            className="w-full"
          />
          {draft.cadence === 'weekly' && (
            <WeekdayPicker
              value={draft.weekday ?? 0}
              onChange={(weekday) => setDraft((current) => ({ ...current, weekday }))}
            />
          )}
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>Время</span>
            <input
              type="time"
              required
              step={300}
              value={draft.time}
              onChange={(event) =>
                setDraft((current) => ({ ...current, time: event.target.value || current.time }))
              }
              className={cn(INPUT_CLASS, 'w-32 tabular-nums')}
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Каждый выпуск берёт новости с прошлого раза: в понедельник по будням это все выходные.
            Время по поясу {zone}.
          </p>
          <ErrorNote error={save.error ?? remove.error} />
          <div className="flex flex-wrap justify-end gap-2">
            {schedule && (
              <Button
                variant="ghost"
                isBusy={remove.isPending}
                onClick={() =>
                  remove.mutate(profile.id, {
                    onSuccess: () => {
                      setOpen(false)
                      toast('Расписание отключено')
                    },
                  })
                }
              >
                Отключить
              </Button>
            )}
            <Button variant="primary" isBusy={save.isPending} onClick={submit}>
              Сохранить
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
