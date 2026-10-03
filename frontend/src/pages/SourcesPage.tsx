import clsx from 'clsx'
import { motion } from 'motion/react'
import { useSearchParams } from 'react-router'
import { ErrorNote, PageHeader } from '../components/ui'
import { ArticlesList } from '../features/sources/ArticlesList'
import { SourceHealth } from '../features/sources/SourceHealth'
import { SourcesTable } from '../features/sources/SourcesTable'
import { useMe, useMeta, useSources } from '../lib/queries'

const TABS = [
  { id: 'sources', label: 'Источники' },
  { id: 'articles', label: 'Публикации' },
] as const

export function SourcesPage() {
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
        subtitle="Ленты, сайты без ленты и Telegram-каналы, из которых собирается материал, и сами публикации: всё, что ассистент видел, доступно для проверки."
      />
      <div
        className="mb-5 inline-flex gap-1 rounded-xl bg-surface-container p-1"
        role="group"
        aria-label="Раздел"
      >
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={tab === item.id ? 'page' : undefined}
            onClick={() => setSearch(item.id === 'sources' ? {} : { tab: item.id })}
            className={clsx(
              'relative rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
              tab === item.id
                ? 'text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab === item.id && (
              <motion.span
                layoutId="sources-tab"
                className="absolute inset-0 rounded-lg bg-primary shadow-elevation-1"
                transition={{ type: 'spring', stiffness: 480, damping: 38 }}
              />
            )}
            <span className="relative">{item.label}</span>
          </button>
        ))}
      </div>

      {tab === 'sources' ? (
        <>
          <ErrorNote error={sources.error} />
          <SourceHealth />
          {sources.data ? (
            <SourcesTable
              sources={sources.data}
              isAdmin={isAdmin}
              canAdd={isAdmin || Boolean(meta.data?.open_catalog)}
            />
          ) : (
            <div className="skeleton h-96" />
          )}
        </>
      ) : (
        <ArticlesList />
      )}
    </>
  )
}
