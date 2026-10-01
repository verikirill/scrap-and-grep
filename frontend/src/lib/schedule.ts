import type { DigestSchedule } from './api'

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
