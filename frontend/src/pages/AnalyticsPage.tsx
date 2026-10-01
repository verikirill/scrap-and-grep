import { useState } from 'react'
import { Analytics as AnalyticsIcon } from '../components/icons'
import { Segmented } from '../components/Segmented'
import { Card, EmptyState, ErrorNote, PageHeader, SkeletonBlock, Toggle } from '../components/ui'
import {
  Activity,
  Adaptation,
  Categories,
  Days,
  Figures,
  Funnel,
  Panel,
  Ranker,
  Slots,
  Sources,
} from '../features/analytics/Panels'
import type { Analytics } from '../lib/api'
import { formatNumber, formatRelative } from '../lib/format'
import { useAnalytics, useMe } from '../lib/queries'

const PERIODS = [
  { value: '7', label: '7 дней' },
  { value: '30', label: '30 дней' },
  { value: '90', label: '90 дней' },
] as const
type Period = (typeof PERIODS)[number]['value']

function Skeletons() {
  return (
    <div className="space-y-4" role="status" aria-label="Считаем">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <SkeletonBlock key={index} className="h-24" />
        ))}
      </div>
      <SkeletonBlock className="h-64" />
      <SkeletonBlock className="h-64" />
    </div>
  )
}

function Queue({ data }: { data: Analytics }) {
  const parts = []
  if (data.last_event_at) parts.push(`последнее событие ${formatRelative(data.last_event_at)}`)
  if (data.queue && data.queue.waiting >= 0) {
    parts.push(`ждут записи ${formatNumber(data.queue.waiting)}`)
    if (data.queue.set_aside)
      parts.push(`отложено нечитаемых ${formatNumber(data.queue.set_aside)}`)
  }
  return parts.length ? (
    <p className="text-center text-xs text-outline">События: {parts.join(', ')}.</p>
  ) : null
}

function Overview({ data, days }: { data: Analytics; days: number }) {
  const totals = data.totals
  if (!totals || totals.seen + totals.served === 0) {
    return (
      <Card>
        <EmptyState icon={<AnalyticsIcon size={22} />} title="Событий за период пока нет">
          Откройте ленту или выпуск: через минуту показы и отметки появятся здесь.
        </EmptyState>
      </Card>
    )
  }
  return (
    <div className="space-y-4">
      <Figures totals={totals} previous={data.previous} />
      <p className="text-xs text-outline">Стрелки: изменение к предыдущим {days} дням.</p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel
          title="От показа к отметке"
          hint="Пары «читатель и статья»: открытая дважды считается один раз. Увиденной считается и статья, открытая раньше, чем успел засчитаться показ."
        >
          <Funnel totals={totals} />
        </Panel>
        <Panel title="По дням" hint="Дни по UTC.">
          <Days daily={data.daily} />
        </Panel>
      </div>
      <Panel title="Что ещё происходило">
        <Activity totals={totals} />
      </Panel>
      <Panel
        title="Места в ленте и выпусках"
        hint="Тонкая линия поверх полосы: разброс, в котором доля открытий могла оказаться случайно. Если линии двух строк перекрываются, разница может быть случайной."
      >
        <Slots slots={data.slots} />
      </Panel>
      <Panel title="Источники" hint="Только источники, у которых увидели хотя бы 30 статей.">
        <Sources data={data} />
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Категории">
          <Categories categories={data.categories} />
        </Panel>
        <Panel
          title="Подстройка профилей"
          hint="Это разные читатели, а не эксперимент: разница подсказывает, но не доказывает."
        >
          <Adaptation cohorts={data.adaptation} />
        </Panel>
      </div>
      <Panel
        title="Ранжирование ленты"
        hint="Пока модель включена, читатели поделены на две постоянные группы: одна получает её порядок, другая остаётся на ручных весах. Сравнивать стоит только эти две строки."
      >
        <Ranker data={data} />
      </Panel>
      <Queue data={data} />
    </div>
  )
}

export function AnalyticsPage() {
  const me = useMe()
  const [period, setPeriod] = useState<Period>('30')
  const [withGuests, setWithGuests] = useState(true)
  const isAdmin = Boolean(me.data?.is_admin && !me.data.is_demo)
  const analytics = useAnalytics(Number(period), withGuests, isAdmin)

  if (me.isError) return <ErrorNote error={me.error} />
  if (me.isSuccess && !isAdmin) {
    return (
      <Card>
        <EmptyState icon={<AnalyticsIcon size={22} />} title="Раздел для администратора">
          Аналитику видит администратор стенда. Роль выдаётся командой radar grant-admin.
        </EmptyState>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Аналитика"
        subtitle="Что читатели видели и что с этим делали: показы, открытия, отметки, выпуски. Только числа, без текстов и адресов."
        actions={
          <>
            <label className="flex items-center gap-2.5 text-sm text-muted-foreground">
              <Toggle checked={withGuests} onChange={setWithGuests} label="Учитывать гостей" />
              <span aria-hidden>Гости</span>
            </label>
            <Segmented label="Период" value={period} onChange={setPeriod} options={PERIODS} />
          </>
        }
      />
      <ErrorNote error={analytics.error} />
      {analytics.data && !analytics.data.enabled ? (
        <Card>
          <EmptyState icon={<AnalyticsIcon size={22} />} title="События выключены">
            Задайте RADAR_CLICKHOUSE_URL, и показы с отметками начнут записываться. В стеке docker
            compose он задан по умолчанию.
          </EmptyState>
        </Card>
      ) : analytics.data ? (
        <Overview data={analytics.data} days={Number(period)} />
      ) : (
        !analytics.error && <Skeletons />
      )}
    </>
  )
}
