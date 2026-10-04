import clsx from 'clsx'

import { Collapsible } from '../../components/Collapsible'
import { Chip } from '../../components/ui'
import type { FetchMethod } from '../../lib/api'
import {
  FETCH_HINTS,
  FETCH_LABELS,
  KIND_HINTS,
  KIND_LABELS,
  PROXY_HINT,
} from '../../lib/sourceList'

// The colours of the dot before a source's name, as StatusDot gives them.
const DOTS = [
  ['bg-success', 'опрошен без ошибок'],
  ['bg-destructive', 'последний опрос с ошибкой'],
  ['bg-outline', 'ещё не опрашивался'],
  ['bg-outline-variant', 'выключен'],
] as const

// One row per word: two kinds share «Страница».
const KINDS = [
  ...new Map(
    Object.entries(KIND_LABELS).map(([kind, label]) => [
      label,
      KIND_HINTS[kind as keyof typeof KIND_HINTS] ?? '',
    ]),
  ),
]

const STEPS = Object.keys(FETCH_LABELS) as Exclude<FetchMethod, 'plain'>[]

function Row({ chip, text }: { chip: React.ReactNode; text: string }) {
  return (
    <li className="flex items-start gap-2.5">
      <span className="shrink-0">{chip}</span>
      <span className="pt-1.5 text-xs text-muted-foreground">{text}</span>
    </li>
  )
}

/**
 * What the dots, chips and numbers of the sources table mean, written out:
 * the hints on hover are for the details, not for learning the table.
 */
export function SourcesLegend() {
  return (
    <div className="border-b border-outline-variant px-5 py-3">
      <Collapsible
        storageKey="sources-legend"
        title="обозначения"
        head={
          <p className="text-sm">
            <span className="font-medium">Обозначения</span>
            <span className="text-muted-foreground">
              {' '}
              · у чипа со знаком «?» есть подсказка при наведении
            </span>
          </p>
        }
      >
        <div className="mt-3 space-y-4">
          <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted-foreground">
            {DOTS.map(([color, text]) => (
              <li key={color} className="flex items-center gap-2">
                <span className={clsx('size-2 rounded-full', color)} aria-hidden />
                {text}
              </li>
            ))}
          </ul>
          <section>
            <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
              Откуда берутся статьи, если у источника нет RSS-ленты
            </h4>
            <ul className="grid gap-2 lg:grid-cols-2">
              {KINDS.map(([label, text]) => (
                <Row key={label} chip={<Chip>{label}</Chip>} text={text} />
              ))}
            </ul>
          </section>
          <section>
            <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
              Как читается сайт, который не пускает простой запрос
            </h4>
            <ul className="grid gap-2 lg:grid-cols-2">
              {STEPS.map((step) => (
                <Row
                  key={step}
                  chip={<Chip tone="spark">{FETCH_LABELS[step]}</Chip>}
                  text={FETCH_HINTS[step]}
                />
              ))}
              <Row chip={<Chip tone="spark">через прокси</Chip>} text={PROXY_HINT} />
            </ul>
          </section>
          <ul className="grid gap-2 lg:grid-cols-2">
            <Row chip={<Chip>RU</Chip>} text="Язык публикаций источника." />
            <Row
              chip={
                <span className="tabular inline-flex h-7 items-center text-xs text-muted-foreground">
                  1 234<span className="ml-1.5 text-success">+12</span>
                </span>
              }
              text="Публикаций всего и новых за сутки."
            />
          </ul>
        </div>
      </Collapsible>
    </div>
  )
}
