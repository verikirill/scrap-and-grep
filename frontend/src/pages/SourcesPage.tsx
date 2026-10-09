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
        subtitle="Каталог RSS-лент, сайтов и Telegram-каналов, а также собранные публикации с возможностью проверки первоисточника."
      />
      <div
        className="mb-5 inline-flex gap-1 rounded-xl bg-surface-secondary p-1"
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
              tab === item.id ? 'text-foreground' : 'text-muted hover:text-foreground',
            )}
          >
            {tab === item.id && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="absolute inset-0 rounded-lg bg-surface shadow-surface"
                transition={{ duration: 0.15 }}
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
            <div className="skeleton skeleton--shimmer rounded-xl h-96" />
          )}
        </>
      ) : (
        <ArticlesList />
      )}
    </>
  )
}
