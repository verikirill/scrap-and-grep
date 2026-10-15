import clsx from 'clsx'
import { motion } from 'motion/react'
import { useId } from 'react'
import type { ReactNode } from 'react'
import { EASE } from '../../components/tokens'
import { formatDay, formatPercent } from '../../lib/analyticsFormat'
import { formatNumber } from '../../lib/format'

const WIDTH = 600
const HEIGHT = 160

/** The middle of a day's slot: bars and line points of one day stand one above the other. */
const slotCenter = (index: number, count: number) => ((index + 0.5) * WIDTH) / Math.max(1, count)

/** Labels under a chart: the first day, the middle one and the last. */
function DayAxis({ days }: { days: string[] }) {
  if (!days.length) return null
  const middle = days[Math.floor(days.length / 2)]
  return (
    <div className="mt-2 flex justify-between text-[11px] text-muted tabular-nums">
      <span>{formatDay(days[0])}</span>
      {days.length > 2 && <span>{formatDay(middle)}</span>}
      <span>{formatDay(days[days.length - 1])}</span>
    </div>
  )
}

/** The chart's name on the left and its top value on the right. */
function ChartCaption({ label, top }: { label: string; top?: string }) {
  return (
    <figcaption className="mb-3 flex items-baseline justify-between gap-3 text-xs">
      <span className="font-medium text-foreground">{label}</span>
      {top && <span className="shrink-0 text-muted tabular-nums">{top}</span>}
    </figcaption>
  )
}

/** Quiet guides: a solid baseline, a dashed middle and top. */
function Guides() {
  return (
    <g className="stroke-separator">
      <line x1={0} x2={WIDTH} y1={HEIGHT} y2={HEIGHT} vectorEffect="non-scaling-stroke" />
      {[HEIGHT / 2, 1].map((y) => (
        <line
          key={y}
          x1={0}
          x2={WIDTH}
          y1={y}
          y2={y}
          strokeDasharray="2 5"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </g>
  )
}

/** The plot area, with a line of text over it when there is nothing to draw. */
function Plot({ children, empty }: { children: ReactNode; empty: string | null }) {
  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="h-36 w-full overflow-visible"
        aria-hidden
      >
        {children}
      </svg>
      {empty && (
        <p className="absolute inset-0 grid place-items-center px-4 text-center text-xs text-muted">
          <span className="rounded-full bg-surface px-3 py-1 ring-1 ring-separator">{empty}</span>
        </p>
      )}
    </div>
  )
}

/**
 * Counts per day as bars from zero, with the peak named at the top. Every day
 * has a faint slot, so a period with few active days reads as such.
 */
export function DayBars({
  days,
  values,
  label,
}: {
  days: string[]
  values: number[]
  label: string
}) {
  // An id that url(#…) takes as is, whatever characters React puts in it.
  const gradient = `day-bars-${useId().replace(/[^\w-]/g, '')}`
  const peak = Math.max(0, ...values)
  const step = WIDTH / Math.max(1, values.length)
  const width = Math.max(1, step * 0.62)
  return (
    <figure>
      <ChartCaption label={label} top={peak ? `до ${formatNumber(peak)}` : undefined} />
      <Plot empty={peak ? null : 'За период показов не было'}>
        <defs>
          <linearGradient id={gradient} x1="0" x2="0" y1="1" y2="0">
            <stop offset="0" style={{ stopColor: 'var(--cta-from)' }} />
            <stop offset="1" style={{ stopColor: 'var(--cta-to)' }} />
          </linearGradient>
        </defs>
        <Guides />
        {values.map((value, index) => {
          const x = slotCenter(index, values.length) - width / 2
          const height = peak ? Math.max(value ? 3 : 0, (value / peak) * (HEIGHT - 2)) : 0
          return (
            <g key={days[index]}>
              <rect
                x={x}
                y={0}
                width={width}
                height={HEIGHT}
                rx={Math.min(4, width / 2)}
                className="fill-default opacity-50"
              />
              <motion.rect
                x={x}
                width={width}
                rx={Math.min(4, width / 2)}
                initial={{ y: HEIGHT, height: 0 }}
                animate={{ y: HEIGHT - height, height }}
                transition={{ duration: 0.5, ease: EASE, delay: Math.min(0.3, index * 0.01) }}
                fill={`url(#${gradient})`}
              >
                <title>{`${formatDay(days[index])}: ${formatNumber(value)}`}</title>
              </motion.rect>
            </g>
          )
        })}
      </Plot>
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
  /** A text colour class: the line and its swatch in the legend take it. */
  tone: string
  values: (number | null)[]
}

/** One line of a chart: known days joined, a lone day as a dot. */
function SeriesLine({
  line,
  x,
  y,
}: {
  line: Series
  x: (index: number) => number
  y: (value: number) => number
}) {
  // Consecutive known days make one segment; a gap breaks the line.
  const segments: string[][] = [[]]
  line.values.forEach((value, index) => {
    if (value === null) segments.push([])
    else segments[segments.length - 1].push(`${x(index)},${y(value)}`)
  })
  return (
    <g className={line.tone}>
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
              strokeWidth={8}
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
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.7, ease: EASE }}
          />
        ))}
    </g>
  )
}

/**
 * Rates per day as lines from zero. Days with too little seen are gaps, not
 * zeros. A legend under the chart names each line with its last known rate.
 */
export function RateLines({
  days,
  series,
  label,
  note,
}: {
  days: string[]
  series: Series[]
  label: string
  /** A short remark under the legend, such as which days are left out. */
  note?: string
}) {
  const known = series.flatMap((line) =>
    line.values.filter((value): value is number => value !== null),
  )
  const top = Math.max(0.05, ...known) * 1.15
  const x = (index: number) => slotCenter(index, days.length)
  const y = (value: number) => HEIGHT - (value / top) * HEIGHT
  return (
    <figure>
      <ChartCaption label={label} top={known.length ? `до ${formatPercent(top)}` : undefined} />
      <Plot empty={known.length ? null : 'Мало показов, чтобы считать долю по дням'}>
        <Guides />
        {series.map((line) => (
          <SeriesLine key={line.label} line={line} x={x} y={y} />
        ))}
      </Plot>
      <DayAxis days={days} />
      <ul className="mt-3 flex flex-wrap gap-1.5 text-xs">
        {series.map((line) => {
          const last = [...line.values].reverse().find((value) => value !== null)
          return (
            <li
              key={line.label}
              className="inline-flex items-center gap-1.5 rounded-full bg-surface-secondary px-2.5 py-1"
            >
              <span className={clsx('h-1 w-3 shrink-0 rounded-full bg-current', line.tone)} />
              <span className="text-muted">{line.label}</span>
              {last != null && (
                <span className="font-semibold tabular-nums">{formatPercent(last)}</span>
              )}
            </li>
          )
        })}
      </ul>
      {note && <p className="mt-2 text-[11px] text-muted">{note}</p>}
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

export type BarTone = 'accent' | 'warning' | 'danger' | 'muted'

// The main measure takes the call-to-action gradient; marks keep their own colours.
const FILLS: Record<BarTone, string> = {
  accent: 'rate-fill',
  warning: 'bg-warning',
  danger: 'bg-danger',
  muted: 'bg-muted/25',
}

/**
 * A rate as a bar from zero with its interval as a whisker across, so two
 * rows can be told apart from noise at a glance.
 */
export function RateBar({
  rate,
  low,
  high,
  scale,
  tone = 'accent',
}: {
  rate: number
  low?: number
  high?: number
  /** The rate that fills the whole track. */
  scale: number
  tone?: BarTone
}) {
  const share = (value: number) => `${Math.min(100, (value / Math.max(scale, 1e-9)) * 100)}%`
  return (
    <div className="relative h-2 w-full rounded-full bg-default">
      <motion.div
        className={clsx('h-full rounded-full', FILLS[tone])}
        initial={{ width: 0 }}
        animate={{ width: share(rate) }}
        transition={{ duration: 0.6, ease: EASE }}
      />
      {low !== undefined && high !== undefined && (
        <div
          className={clsx(
            'absolute top-1/2 h-3 -translate-y-1/2',
            tone === 'muted' ? 'text-muted' : 'rate-interval',
          )}
          style={{ left: share(low), width: `calc(${share(high)} - ${share(low)})` }}
          title={`от ${formatPercent(low)} до ${formatPercent(high)}`}
        >
          <span className="rate-interval__part absolute inset-x-0 top-1/2 h-px -translate-y-1/2" />
          <span className="rate-interval__part rate-interval__end absolute inset-y-0 left-0 w-0.5" />
          <span className="rate-interval__part rate-interval__end absolute inset-y-0 right-0 w-0.5" />
        </div>
      )}
    </div>
  )
}
