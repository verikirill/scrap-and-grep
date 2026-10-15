import { useState } from 'react'
import {
  Analytics as AnalyticsIcon,
  CalendarMonth,
  DynamicFeed,
  Layers,
  ListOrdered,
  Rss,
  SlidersHorizontal,
  Sparkles,
  Target,
} from '../components/icons'
import { Segmented } from '../components/Segmented'
import { Loading, Skeleton, SkeletonChart } from '../components/loading'
import { Card, EmptyState, ErrorState, PageHeader, Toggle } from '../components/ui'
import { Activity, Days, Figures, Funnel, Panel } from '../features/analytics/Panels'
import { Adaptation, Categories, Ranker, Slots, Sources } from '../features/analytics/tables'
import type { Analytics } from '../lib/api'
import { formatNumber, formatRelative } from '../lib/format'
import { useAnalytics, useMe } from '../lib/queries'

const PERIODS = [
  { value: '7', label: '7 дней' },
  { value: '30', label: '30 дней' },
  { value: '90', label: '90 дней' },
] as const
type Period = (typeof PERIODS)[number]['value']

const ICON = 20

function Skeletons() {
  return (
    <Loading label="Считаем" className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <div key={index} className="space-y-3 rounded-3xl bg-surface p-4 shadow-surface sm:p-5">
            <div className="flex items-center gap-2.5">
              <Skeleton className="size-8 rounded-xl" />
              <Skeleton className="h-3 w-20" />
            </div>
            <Skeleton className="h-7 w-16" />
            <Skeleton className="h-5 w-24 rounded-full" />
          </div>
        ))}
      </div>
      <SkeletonChart />
      <SkeletonChart />
    </Loading>
  )
}

/** How fresh the numbers are: the last event and the queue still to be written. */
function queueText(data: Analytics): string | null {
  const parts = []
  if (data.last_event_at) parts.push(`последнее событие ${formatRelative(data.last_event_at)}`)
  if (data.queue && data.queue.waiting >= 0) {
    parts.push(`ждут записи ${formatNumber(data.queue.waiting)}`)
    if (data.queue.set_aside)
      parts.push(`отложено нечитаемых ${formatNumber(data.queue.set_aside)}`)
  }
  return parts.length ? `События: ${parts.join(', ')}.` : null
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
      <Figures totals={totals} previous={data.previous} days={days} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel
          icon={<Target size={ICON} />}
          title="От показа к отметке"
          subtitle="Каждая пара «читатель и статья» считается один раз"
          note="Открытая статья считается и увиденной."
        >
          <Funnel totals={totals} />
        </Panel>
        <Panel
          icon={<CalendarMonth size={ICON} />}
          title="По дням"
          subtitle="Показы и доли за каждый день, дни по UTC"
        >
          <Days daily={data.daily} />
        </Panel>
      </div>
      <Panel
        icon={<Sparkles size={ICON} />}
        title="Что ещё происходило"
        subtitle="Лента, выпуски, запросы через MCP и предложения подстройки"
        note={queueText(data)}
      >
        <Activity totals={totals} />
      </Panel>
      <Panel
        icon={<DynamicFeed size={ICON} />}
        title="Места в ленте и выпусках"
        subtitle="Как часто открывают статьи в каждом месте, где их показали"
        note="Отрезок на полосе показывает доверительный интервал. Если отрезки пересекаются, разница между показателями может быть случайной."
      >
        <Slots slots={data.slots} />
      </Panel>
      <Panel
        icon={<Rss size={ICON} />}
        title="Источники"
        subtitle="Только источники, у которых увидели хотя бы 30 статей"
      >
        <Sources data={data} />
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel
          icon={<Layers size={ICON} />}
          title="Категории"
          subtitle="Как часто открывают статьи каждой категории"
        >
          <Categories categories={data.categories} />
        </Panel>
        <Panel
          icon={<SlidersHorizontal size={ICON} />}
          title="Подстройка профилей"
          subtitle="Читатели с автоподстройкой профиля и без неё"
          note="В группах разные читатели, поэтому разница между ними не доказывает эффект подстройки."
        >
          <Adaptation cohorts={data.adaptation} />
        </Panel>
      </div>
      <Panel
        icon={<ListOrdered size={ICON} />}
        title="Ранжирование ленты"
        subtitle="Ручные веса и обученная модель по группам читателей"
        note="При активной модели читатели поделены на две постоянные группы: модельную и контрольную (на ручных весах). Сравнивать корректно только эти две строки."
      >
        <Ranker data={data} />
      </Panel>
    </div>
  )
}

export function AnalyticsPage() {
  const me = useMe()
  const [period, setPeriod] = useState<Period>('30')
  const [withGuests, setWithGuests] = useState(true)
  const isAdmin = Boolean(me.data?.is_admin && !me.data.is_demo)
  const analytics = useAnalytics(Number(period), withGuests, isAdmin)

  if (me.isError) {
    return (
      <Card>
        <ErrorState title="Не удалось проверить доступ" error={me.error} />
      </Card>
    )
  }
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
            {/* White with an edge, as the period beside it: the dots must not show through. */}
            <label className="flex h-10 items-center gap-2.5 rounded-full bg-surface pr-4 pl-1.5 text-[13px] font-medium ring-1 ring-border">
              <Toggle checked={withGuests} onChange={setWithGuests} label="Учитывать гостей" />
              <span aria-hidden>Гости</span>
            </label>
            <Segmented label="Период" value={period} onChange={setPeriod} options={PERIODS} />
          </>
        }
      />
      {analytics.error ? (
        <Card>
          <ErrorState title="Аналитика не загрузилась" error={analytics.error} />
        </Card>
      ) : analytics.data && !analytics.data.enabled ? (
        <Card>
          <EmptyState icon={<AnalyticsIcon size={22} />} title="События выключены">
            На этом стенде не подключено хранилище событий, поэтому показы и отметки не
            записываются.
          </EmptyState>
        </Card>
      ) : analytics.data ? (
        <Overview data={analytics.data} days={Number(period)} />
      ) : (
        <Skeletons />
      )}
    </>
  )
}
