import { Card, Chip } from '../../components/ui'
import type { SourceHealth as Health } from '../../lib/api'
import { formatNumber, formatRelative, pause, plural } from '../../lib/format'
import { useSourceHealth } from '../../lib/queries'

function Summary({ health }: { health: Health }) {
  const share = health.polls ? Math.round((health.ok / health.polls) * 100) : null
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <p className="text-sm">
        <span className="font-semibold">Здоровье за сутки:</span>{' '}
        {health.polls === 0 ? (
          'опросов ещё не было'
        ) : (
          <>
            {formatNumber(health.polls)} {plural(health.polls, ['опрос', 'опроса', 'опросов'])},{' '}
            <span className={share !== null && share < 90 ? 'text-destructive' : 'text-success'}>
              {share}% успешных
            </span>
          </>
        )}
      </p>
      {Object.entries(health.errors).map(([kind, count]) => (
        <Chip key={kind} tone="danger" title="Неудачных опросов этого рода за сутки">
          {health.kinds[kind] ?? kind}: {count}
        </Chip>
      ))}
    </div>
  )
}

/**
 * How the sources are doing: the share of good polls in a day, the errors by
 * kind, the sources that fail and those silent longer than usual for them.
 */
export function SourceHealth() {
  const health = useSourceHealth()
  if (!health.data) return null
  const { failing, silent, kinds } = health.data
  return (
    <Card className="mb-5 space-y-3 px-5 py-4">
      <Summary health={health.data} />
      {failing.length === 0 && silent.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Все источники читаются, и никто не молчит дольше обычного.
        </p>
      )}
      {failing.length > 0 && (
        <section>
          <h3 className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Не читаются
          </h3>
          <ul className="space-y-1 text-sm">
            {failing.map((item) => (
              <li key={item.source_id} title={item.error ?? undefined}>
                <span className="font-medium">{item.name}</span>
                <span className="text-muted-foreground">
                  {' '}
                  - {kinds[item.kind ?? 'other'] ?? item.kind}, {item.failures}{' '}
                  {plural(item.failures, ['неудача', 'неудачи', 'неудач'])} подряд
                  {item.since && `, последний удачный опрос ${formatRelative(item.since)}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {silent.length > 0 && (
        <section>
          <h3 className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Молчат дольше обычного
          </h3>
          <ul className="space-y-1 text-sm">
            {silent.map((item) => (
              <li key={item.source_id}>
                <span className="font-medium">{item.name}</span>
                <span className="text-muted-foreground">
                  {' '}
                  - последняя публикация {formatRelative(item.last_article)}, а самая долгая пауза
                  за месяц - {pause(item.longest_gap_hours)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Card>
  )
}
