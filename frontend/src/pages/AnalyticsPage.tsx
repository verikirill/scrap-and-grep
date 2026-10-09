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
    <p className="text-center text-xs text-muted">События: {parts.join(', ')}.</p>
  ) : null
}

function Overview({ data, days }: { data: Analytics; days: number }) {
  const totals = data.totals
  if (!totals || totals.seen + totals.served === 0) {
    return (
      <Card>
        <EmptyState icon={<AnalyticsIcon size={22} />} title="Событий за период пока нет">
          Показы и отметки появляются здесь в течение минуты после того, как читатель открыл ленту
          или выпуск.
        </EmptyState>
      </Card>
    )
  }
  return (
    <div className="space-y-4">
      <Figures totals={totals} previous={data.previous} />
      <p className="text-xs text-muted">Стрелки: изменение к предыдущим {days} дням.</p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel
          title="От показа к отметке"
          hint="Каждая пара «читатель и статья» считается один раз. Открытая статья считается и увиденной."
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
        hint="Отрезок на полосе показывает доверительный интервал. Если отрезки пересекаются, разница между показателями может быть случайной."
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
          hint="В группах разные читатели, поэтому разница между ними не доказывает эффект подстройки."
        >
          <Adaptation cohorts={data.adaptation} />
        </Panel>
      </div>
      <Panel
        title="Ранжирование ленты"
        hint="При активной модели читатели поделены на две постоянные группы: модельную и контрольную (на ручных весах). Сравнивать корректно только эти две строки."
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
          Аналитику видит администратор стенда.
        </EmptyState>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Аналитика"
        subtitle="Активность читателей: показы, открытия, отметки и собранные выпуски. Только обезличенные числовые данные."
        actions={
          <>
            <label className="flex items-center gap-2.5 text-sm text-muted">
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
            На этом стенде не подключено хранилище событий, поэтому показы и отметки не
            записываются.
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
