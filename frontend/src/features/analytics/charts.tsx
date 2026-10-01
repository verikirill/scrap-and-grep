import clsx from 'clsx'
import { motion } from 'motion/react'
import { EASE } from '../../components/tokens'
import { formatNumber } from '../../lib/format'

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

const WIDTH = 600
const HEIGHT = 160

/** Labels under a chart: the first day, the middle one and the last. */
function DayAxis({ days }: { days: string[] }) {
  if (!days.length) return null
  const middle = days[Math.floor(days.length / 2)]
  return (
    <div className="mt-1.5 flex justify-between text-[11px] text-outline tabular-nums">
      <span>{formatDay(days[0])}</span>
      {days.length > 2 && <span>{formatDay(middle)}</span>}
      <span>{formatDay(days[days.length - 1])}</span>
    </div>
  )
}

/** Counts per day as bars from zero, with the peak named at the top. */
export function DayBars({
  days,
  values,
  label,
}: {
  days: string[]
  values: number[]
  label: string
}) {
  const peak = Math.max(1, ...values)
  const step = WIDTH / Math.max(1, values.length)
  return (
    <figure>
      <figcaption className="mb-2 flex items-baseline justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="tabular-nums">до {formatNumber(peak)}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="h-36 w-full text-primary"
        aria-hidden
      >
        <line x1={0} x2={WIDTH} y1={HEIGHT} y2={HEIGHT} className="stroke-outline-variant" />
        {values.map((value, index) => {
          const height = (value / peak) * (HEIGHT - 4)
          return (
            <motion.rect
              key={days[index]}
              x={index * step + step * 0.15}
              width={step * 0.7}
              rx={Math.min(3, step * 0.2)}
              initial={{ y: HEIGHT, height: 0 }}
              animate={{ y: HEIGHT - height, height }}
              transition={{ duration: 0.5, ease: EASE, delay: Math.min(0.3, index * 0.01) }}
              className="fill-current"
            >
              <title>{`${formatDay(days[index])}: ${formatNumber(value)}`}</title>
            </motion.rect>
          )
        })}
      </svg>
      <DayAxis days={days} />
      {/* A table ignores the 1px width of sr-only and would stretch the page. */}
      <div className="sr-only">
        <table>
          <caption>{label}</caption>
          <tbody>
            {values.map((value, index) => (
              <tr key={days[index]}>
                <th scope="row">{formatDay(days[index])}</th>
                <td>{formatNumber(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  )
}

export type Series = {
  label: string
  /** A text colour class: the line and its label take it. */
  tone: string
  values: (number | null)[]
}

/**
 * Rates per day as lines from zero. Days with too little seen are gaps, not
 * zeros. Each line is named at its end instead of in a legend.
 */
export function RateLines({
  days,
  series,
  label,
}: {
  days: string[]
  series: Series[]
  label: string
}) {
  const known = series.flatMap((line) =>
    line.values.filter((value): value is number => value !== null),
  )
  const top = Math.max(0.05, ...known) * 1.15
  const x = (index: number) => (days.length > 1 ? (index / (days.length - 1)) * WIDTH : WIDTH / 2)
  const y = (value: number) => HEIGHT - (value / top) * HEIGHT
  return (
    <figure>
      <figcaption className="mb-2 flex items-baseline justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="tabular-nums">до {formatPercent(top)}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="h-36 w-full"
        aria-hidden
      >
        <line x1={0} x2={WIDTH} y1={HEIGHT} y2={HEIGHT} className="stroke-outline-variant" />
        <line
          x1={0}
          x2={WIDTH}
          y1={HEIGHT / 2}
          y2={HEIGHT / 2}
          className="stroke-outline-variant"
          strokeDasharray="4 6"
        />
        {series.map((line) => {
          // Consecutive known days make one segment; a gap breaks the line.
          const segments: string[][] = [[]]
          line.values.forEach((value, index) => {
            if (value === null) segments.push([])
            else segments[segments.length - 1].push(`${x(index)},${y(value)}`)
          })
          return (
            <g key={line.label} className={line.tone}>
              {/* A day with no known neighbour is a dot, not nothing. */}
              {segments
                .filter((points) => points.length === 1)
                .map((points) => {
                  // A round-capped stroke of almost no length: a dot whatever the scale.
                  const [cx, cy] = points[0].split(',').map(Number)
                  return (
                    <line
                      key={points[0]}
                      x1={cx - 0.01}
                      x2={cx + 0.01}
                      y1={cy}
                      y2={cy}
                      stroke="currentColor"
                      strokeWidth={7}
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  )
                })}
              {segments
                .filter((points) => points.length > 1)
                .map((points) => (
                  <motion.polyline
                    key={points[0]}
                    points={points.join(' ')}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    vectorEffect="non-scaling-stroke"
                    strokeLinejoin="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.7, ease: EASE }}
                  />
                ))}
            </g>
          )
        })}
      </svg>
      <DayAxis days={days} />
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {series.map((line) => {
          const last = [...line.values].reverse().find((value) => value !== null)
          return (
            <li key={line.label} className="flex items-center gap-1.5">
              <span className={clsx('h-0.5 w-4 rounded-full bg-current', line.tone)} />
              <span className="text-muted-foreground">{line.label}</span>
              {last != null && (
                <span className="font-medium tabular-nums">{formatPercent(last)}</span>
              )}
            </li>
          )
        })}
      </ul>
      {/* A table ignores the 1px width of sr-only and would stretch the page. */}
      <div className="sr-only">
        <table>
          <caption>{label}</caption>
          <thead>
            <tr>
              <th scope="col">День</th>
              {series.map((line) => (
                <th key={line.label} scope="col">
                  {line.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {days.map((day, index) => (
              <tr key={day}>
                <th scope="row">{formatDay(day)}</th>
                {series.map((line) => (
                  <td key={line.label}>
                    {line.values[index] === null
                      ? 'мало данных'
                      : formatPercent(line.values[index] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  )
}

/**
 * A rate as a bar from zero with its interval as a thin line across, so two
 * rows can be told apart from noise at a glance.
 */
export function RateBar({
  rate,
  low,
  high,
  scale,
  tone = 'text-primary',
}: {
  rate: number
  low?: number
  high?: number
  /** The rate that fills the whole track. */
  scale: number
  tone?: string
}) {
  const share = (value: number) => `${Math.min(100, (value / Math.max(scale, 1e-9)) * 100)}%`
  return (
    <div className={clsx('relative h-2.5 w-full rounded-full bg-surface-container-highest', tone)}>
      <motion.div
        className="h-full rounded-full bg-current"
        initial={{ width: 0 }}
        animate={{ width: share(rate) }}
        transition={{ duration: 0.6, ease: EASE }}
      />
      {low !== undefined && high !== undefined && (
        <div
          className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-on-surface/55"
          style={{ left: share(low), width: `calc(${share(high)} - ${share(low)})` }}
          title={`от ${formatPercent(low)} до ${formatPercent(high)}`}
        />
      )}
    </div>
  )
}
