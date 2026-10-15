// The administrator's analytics: counts over reader-article pairs with their
// rates worked out as the server does (backend events/analytics.py), the
// overview of a period and the nightly runs of the feed's ranker.
import type { Analytics, AnalyticsTotals, RankerRun, Rates } from '../../lib/api'
import { daysBefore } from './catalog'

const Z = 1.96
const MIN_SEEN = 30

/** The 95% Wilson interval of a share. */
function wilson(successes: number, trials: number): [number, number] {
  if (trials <= 0) return [0, 0]
  const rate = successes / trials
  const spread = Z * Math.sqrt((rate * (1 - rate)) / trials + (Z * Z) / (4 * trials * trials))
  const centre = rate + (Z * Z) / (2 * trials)
  const scale = 1 + (Z * Z) / trials
  return [Math.max(0, (centre - spread) / scale), Math.min(1, (centre + spread) / scale)]
}

/** 1,200 seen and 180 opened by default; the rates follow the counts given. */
export function makeRates(overrides: Partial<Rates> = {}): Rates {
  const { seen = 1200, opened = 180, liked = 40, rejected = 25 } = overrides
  const [low, high] = wilson(opened, seen)
  return {
    seen,
    opened,
    liked,
    rejected,
    ctr: seen ? opened / seen : 0,
    ctr_low: low,
    ctr_high: high,
    like_rate: seen ? liked / seen : 0,
    reject_rate: seen ? rejected / seen : 0,
    enough: seen >= MIN_SEEN,
    ...overrides,
  }
}

export function makeAnalyticsTotals(overrides: Partial<AnalyticsTotals> = {}): AnalyticsTotals {
  return {
    ...makeRates(overrides),
    readers: 48,
    served: 5400,
    digests_built: 36,
    digests_opened: 52,
    mcp_calls: 14,
    suggestions_accepted: 5,
    suggestions_dismissed: 3,
    ...overrides,
  }
}

/** Last night's run: the model beat the hand weights and was switched on. */
export function makeRankerRun(overrides: Partial<RankerRun> = {}): RankerRun {
  return {
    version: '20261014-021500',
    status: 'active',
    created_at: '2026-10-14T02:15:00Z',
    lists: 820,
    rows: 16_400,
    hand_ndcg: 0.412,
    model_ndcg: 0.447,
    note: 'Модель лучше ручных весов на +0.035 nDCG@20 на последних днях, у 37 читателей.',
    ...overrides,
  }
}

const LOST_RUN: Partial<RankerRun> = {
  status: 'rejected',
  model_ndcg: 0.408,
  note: 'Модель не обогнала ручные веса: -0.004 nDCG@20 (нижняя граница -0.021), нужно +0.010 и граница выше нуля.',
}

/** `count` nightly runs, newest first: the active one, then runs that lost to the hand weights. */
export function makeRankerRuns(count: number, overrides: Partial<RankerRun> = {}): RankerRun[] {
  return Array.from({ length: count }, (_, index) => {
    const created_at = daysBefore(index, '02:15')
    // "20261014-021500": the night's time, as the trainer names a run.
    const version = created_at.slice(0, 19).replace(/[-:]/g, '').replace('T', '-')
    return makeRankerRun({ version, created_at, ...(index > 0 ? LOST_RUN : {}), ...overrides })
  })
}

type DayCounts = Pick<Rates, 'seen' | 'opened' | 'liked' | 'rejected'> & { readers: number }

const QUIET_DAY: DayCounts = { seen: 0, opened: 0, liked: 0, rejected: 0, readers: 0 }

/** The last three days of the period; together they make makeRates()'s counts. */
const BUSY_DAYS: DayCounts[] = [
  { seen: 380, opened: 55, liked: 12, rejected: 8, readers: 19 },
  { seen: 410, opened: 63, liked: 14, rejected: 9, readers: 21 },
  { seen: 410, opened: 62, liked: 14, rejected: 8, readers: 22 },
]

/** A row for each of the 30 days to 2026-10-13, as the server lists them, quiet ones too. */
function dailyRows(): Analytics['daily'] {
  const days = [...new Array<DayCounts>(30 - BUSY_DAYS.length).fill(QUIET_DAY), ...BUSY_DAYS]
  return days.map(({ readers, ...counts }, index) => ({
    ...makeRates(counts),
    day: daysBefore(days.length - index).slice(0, 10),
    readers,
  }))
}

/** Thirty days, guests counted, the learned ranker serving half the readers.
 * Every breakdown adds up to the totals. */
export function makeAnalytics(overrides: Partial<Analytics> = {}): Analytics {
  return {
    enabled: true,
    start: '2026-09-14T00:00:00Z',
    end: '2026-10-14T00:00:00Z',
    guests: true,
    totals: makeAnalyticsTotals(),
    previous: makeAnalyticsTotals({
      seen: 1000,
      opened: 120,
      liked: 28,
      rejected: 24,
      readers: 41,
      served: 4600,
    }),
    daily: dailyRows(),
    slots: [
      { ...makeRates({ seen: 820, opened: 131, liked: 29, rejected: 15 }), slot: 'ranked' },
      { ...makeRates({ seen: 120, opened: 12, liked: 2, rejected: 6 }), slot: 'explore' },
      { ...makeRates({ seen: 40, opened: 14, liked: 4, rejected: 0 }), slot: 'saved' },
      { ...makeRates({ seen: 220, opened: 23, liked: 5, rejected: 4 }), slot: 'digest' },
    ],
    sources_best: [
      {
        ...makeRates({ seen: 420, opened: 88, liked: 21, rejected: 4 }),
        source_id: 1,
        name: 'SecurityLab.ru',
      },
      {
        ...makeRates({ seen: 96, opened: 22, liked: 6, rejected: 1 }),
        source_id: 2,
        name: 'Kaspersky ICS CERT',
      },
    ],
    sources_rejected: [
      {
        ...makeRates({ seen: 160, opened: 9, liked: 1, rejected: 14 }),
        source_id: 4,
        name: 'OpenNET',
      },
    ],
    categories: [
      { ...makeRates({ seen: 640, opened: 104, liked: 24, rejected: 9 }), category: 'security' },
      { ...makeRates({ seen: 230, opened: 41, liked: 10, rejected: 2 }), category: 'ics' },
      { ...makeRates({ seen: 210, opened: 17, liked: 2, rejected: 12 }), category: 'it' },
      { ...makeRates({ seen: 120, opened: 18, liked: 4, rejected: 2 }), category: 'energy' },
    ],
    adaptation: [
      {
        ...makeRates({ seen: 470, opened: 81, liked: 19, rejected: 7 }),
        adaptive: true,
        readers: 18,
      },
      {
        ...makeRates({ seen: 730, opened: 99, liked: 21, rejected: 18 }),
        adaptive: false,
        readers: 30,
      },
    ],
    variants: [
      {
        ...makeRates({ seen: 590, opened: 84, liked: 18, rejected: 13 }),
        variant: 'control',
        readers: 24,
      },
      {
        ...makeRates({ seen: 610, opened: 96, liked: 22, rejected: 12 }),
        variant: 'learned',
        readers: 24,
      },
    ],
    last_event_at: '2026-10-14T08:59:00Z',
    queue: { waiting: 0, set_aside: 0 },
    ranker: { share: 0.5, active: '20261014-021500', runs: [makeRankerRun()] },
    ...overrides,
  }
}
