import clsx from 'clsx'
import { motion } from 'motion/react'
import { useSearchParams } from 'react-router'
import { ErrorNote, PageHeader } from '../components/ui'
import { ArticlesList } from '../features/sources/ArticlesList'
import { SourcesTable } from '../features/sources/SourcesTable'
import { useMe, useSources } from '../lib/queries'

const TABS = [
  { id: 'sources', label: 'Источники' },
  { id: 'articles', label: 'Публикации' },
] as const

export function SourcesPage() {
  const [search, setSearch] = useSearchParams()
  const tab = search.get('tab') === 'articles' ? 'articles' : 'sources'
  const sources = useSources()
  const me = useMe()

  return (
    <>
      <PageHeader
        title="Источники"
        subtitle="Ленты, из которых собирается материал, и сами публикации: всё, что ассистент видел, доступно для проверки."
      />
      <div
        className="mb-5 inline-flex gap-1 rounded-xl bg-sunken p-1"
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
              tab === item.id ? 'text-text' : 'text-muted hover:text-text',
            )}
          >
            {tab === item.id && (
              <motion.span
                layoutId="sources-tab"
                className="absolute inset-0 rounded-lg bg-surface shadow-sm"
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
          {sources.data ? (
            <SourcesTable sources={sources.data} canEdit={Boolean(me.data?.is_admin)} />
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
