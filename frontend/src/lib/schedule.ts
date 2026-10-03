import type { DigestSchedule, ScheduleDefault } from './api'

const ON_DAYS = [
  'по понедельникам',
  'по вторникам',
  'по средам',
  'по четвергам',
  'по пятницам',
  'по субботам',
  'по воскресеньям',
]
/** "по будням в 09:00": a schedule in words. */
export function scheduleLabel(
  schedule: Pick<DigestSchedule, 'cadence' | 'weekday' | 'time'>,
): string {
  const when =
    schedule.cadence === 'daily'
      ? 'каждый день'
      : schedule.cadence === 'weekdays'
        ? 'по будням'
        : ON_DAYS[schedule.weekday ?? 0]
  return `${when} в ${schedule.time}`
}

/** The panel's period for a profile's audience: a day for specialists, a week
 * for management. One the panel does not offer gives way to a week. */
export function periodChoice<T extends string>(days: number | undefined, choices: readonly T[]): T {
  const wanted = choices.find((choice) => choice === String(days))
  return wanted ?? (choices.find((choice) => choice === '7') as T)
}

/** Where the schedule dialog starts for a profile without a schedule. The
 * weekday picker always needs a day, even for a weekday schedule. */
export function scheduleDraft(
  suggested: ScheduleDefault,
): Pick<DigestSchedule, 'cadence' | 'weekday' | 'time'> & { weekday: number } {
  return { cadence: suggested.cadence, weekday: suggested.weekday ?? 0, time: suggested.time }
}
