// Numbers of the analytics page: days of its charts, rates and their changes.

const dayFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})
const percentFormat = new Intl.NumberFormat('ru-RU', {
  style: 'percent',
  maximumFractionDigits: 1,
})

export const formatDay = (iso: string) => dayFormat.format(new Date(iso))
export const formatPercent = (value: number) => percentFormat.format(value)

/** A change in percentage points, signed: "+1,2 п. п.". */
export function formatPoints(delta: number): string {
  const points = Math.round(delta * 1000) / 10
  return `${points > 0 ? '+' : points < 0 ? '−' : ''}${Math.abs(points).toLocaleString('ru-RU')} п. п.`
}
