import { motion } from 'motion/react'
import { Link } from 'react-router'
import { EASE } from '../../components/tokens'
import { Card } from '../../components/ui'
import type { Taste, TasteFacet } from '../../lib/api'
import { plural } from '../../lib/format'

const GROUPS: { kind: TasteFacet['kind']; title: string; empty?: string }[] = [
  { kind: 'interest', title: 'Заявленные интересы', empty: 'Профиль интересов не задан.' },
  { kind: 'resume', title: 'Из резюме', empty: 'Резюме не загружено.' },
  { kind: 'learned', title: 'Выучено по вашим отметкам' },
  { kind: 'avoid', title: 'Показываем реже' },
]

function FacetRow({ facet }: { facet: TasteFacet }) {
  const isAvoid = facet.kind === 'avoid'
  return (
    <li className="flex items-center gap-2.5">
      <span className="h-1 w-8 shrink-0 overflow-hidden rounded-full bg-outline-variant">
        <motion.span
          className={
            isAvoid
              ? 'block h-full origin-left bg-destructive'
              : 'block h-full origin-left bg-primary'
          }
          initial={{ scaleX: 0 }}
          animate={{ scaleX: Math.min(1, facet.weight / 1.5) }}
          transition={{ duration: 0.5, ease: EASE }}
        />
      </span>
      <span className="min-w-0 truncate text-[13px]" title={facet.label}>
        {facet.kind === 'learned' || isAvoid ? `«${facet.label}»` : facet.label}
      </span>
    </li>
  )
}

/** What the recommender believes about the reader, in words they can check. */
export function TastePanel({ taste }: { taste: Taste }) {
  const signals = taste.positives + taste.negatives
  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold">Из чего собрана лента</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        {signals === 0
          ? 'Отметок пока нет. Лента учитывает уже первую.'
          : `${signals} ${plural(signals, ['отметка', 'отметки', 'отметок'])} за последнее время. Старые отметки постепенно теряют вес.`}
      </p>

      <div className="mt-3">
        <div className="flex items-baseline justify-between text-xs">
          <span className="text-muted-foreground">Доверие к отметкам</span>
          <span className="tabular font-semibold">{Math.round(taste.confidence * 100)}%</span>
        </div>
        <div
          role="progressbar"
          aria-label="Доверие к отметкам"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(taste.confidence * 100)}
          className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-container"
        >
          <motion.div
            className="h-full origin-left rounded-full bg-spark"
            initial={false}
            animate={{ scaleX: taste.confidence }}
            transition={{ type: 'spring', stiffness: 90, damping: 20 }}
          />
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {GROUPS.map((group) => {
          const facets = taste.facets.filter((facet) => facet.kind === group.kind)
          if (facets.length === 0 && !group.empty) return null
          return (
            <section key={group.kind}>
              <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {group.title}
              </h3>
              {facets.length > 0 ? (
                <ul className="mt-2 space-y-1.5">
                  {facets.map((facet) => (
                    <FacetRow key={`${facet.kind}-${facet.label}`} facet={facet} />
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-[13px] text-outline">{group.empty}</p>
              )}
            </section>
          )
        })}

        {taste.sources.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Источники
            </h3>
            <ul className="mt-2 space-y-1">
              {taste.sources.map((source) => (
                <li
                  key={source.source_id}
                  className="flex items-baseline justify-between gap-3 text-[13px]"
                >
                  <span className="min-w-0 truncate">{source.name}</span>
                  <span className={source.affinity < 0 ? 'text-destructive' : 'text-success'}>
                    {source.affinity < 0 ? 'реже' : 'чаще'}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <p className="mt-5 border-t border-outline-variant pt-3 text-xs text-muted-foreground">
        Интересы правятся в разделе{' '}
        <Link to="/profiles" className="text-on-primary-container hover:underline">
          «Интересы»
        </Link>
        , резюме — в{' '}
        <Link to="/account" className="text-on-primary-container hover:underline">
          аккаунте
        </Link>
        .
      </p>
    </Card>
  )
}
