import clsx from 'clsx'
import { useRef } from 'react'
import { useSearchParams } from 'react-router'
import { Loading, SkeletonTable } from '../components/loading'
import { Button, Card, ErrorState, PageHeader } from '../components/ui'
import { ArticlesList } from '../features/sources/ArticlesList'
import { SourceHealth } from '../features/sources/SourceHealth'
import { SourcesTable } from '../features/sources/SourcesTable'
import { SlidingPill } from '../components/SlidingPill'
import { useMe, useMeta, useSources } from '../lib/queries'

const TABS = [
  { id: 'sources', label: 'Источники' },
  { id: 'articles', label: 'Публикации' },
] as const

export function SourcesPage() {
  const tabRow = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useSearchParams()
  const tab = search.get('tab') === 'articles' ? 'articles' : 'sources'
  const sources = useSources()
  const me = useMe()
  const meta = useMeta()
  const isAdmin = Boolean(me.data?.is_admin)

  return (
    <>
      <PageHeader
        title="Источники"
        subtitle="Каталог RSS-лент, сайтов и Telegram-каналов, а также собранные публикации с возможностью проверки первоисточника."
      />
      <div
        ref={tabRow}
        className="relative isolate mb-5 inline-flex gap-1 rounded-xl bg-surface-secondary p-1"
        role="group"
        aria-label="Раздел"
      >
        <SlidingPill
          container={tabRow}
          activeKey={tab}
          className="rounded-lg bg-surface shadow-surface"
        />
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={tab === item.id ? 'page' : undefined}
            data-active={tab === item.id}
            onClick={() => setSearch(item.id === 'sources' ? {} : { tab: item.id })}
            className={clsx(
              'relative rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
              tab === item.id ? 'text-foreground' : 'text-muted hover:text-foreground',
            )}
          >
            <span className="relative">{item.label}</span>
          </button>
        ))}
      </div>

      {tab === 'sources' ? (
        <>
          <SourceHealth />
          {sources.error ? (
            <Card>
              <ErrorState
                title="Каталог источников не загрузился"
                error={sources.error}
                action={<Button onClick={() => void sources.refetch()}>Повторить</Button>}
              />
            </Card>
          ) : sources.data ? (
            <SourcesTable
              sources={sources.data}
              isAdmin={isAdmin}
              canAdd={isAdmin || Boolean(meta.data?.open_catalog)}
            />
          ) : (
            <Loading label="Загружаем источники">
              <SkeletonTable rows={8} />
            </Loading>
          )}
        </>
      ) : (
        <ArticlesList />
      )}
    </>
  )
}
