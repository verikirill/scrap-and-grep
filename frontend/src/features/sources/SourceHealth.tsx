import { useState, type ReactNode } from 'react'

import { Collapsible } from '../../components/Collapsible'
import { Help } from '../../components/icons'
import { Card, Chip } from '../../components/ui'
import type { SourceHealth as Health } from '../../lib/api'
import { formatNumber, formatRelative, pause, plural, shareOfGood } from '../../lib/format'
import { useSourceHealth } from '../../lib/queries'

/** What each kind of failed poll means, for the hint on its chip. */
const ERROR_HINTS: Record<string, string> = {
  dns: 'Адрес сайта не находится в DNS: сайт закрылся, сменил домен или не работает DNS.',
  tls: 'Сертификат сайта просрочен или ему нельзя доверять, поэтому соединение не установлено.',
  refused: 'Сайт ответил отказом (401, 403 или 429). Так обычно срабатывает защита от ботов.',
  stub: 'Вместо страницы пришла проверка Cloudflare или DDoS-Guard.',
  timeout: 'Сайт не ответил за отведённое время.',
  connect: 'Соединение с сайтом не установилось или оборвалось.',
  http: 'Сайт вернул ошибку, например 404 или 500.',
  markup:
    'Страница открылась, но статьи на ней больше не находятся. Скорее всего, сайт сменил вёрстку.',
  unsafe: 'Адрес ведёт во внутреннюю сеть, а такие адреса сервис не читает.',
  other: 'Ошибка другого рода. Её текст виден в подсказке у источника.',
}

// Longer lists open on demand: twenty silent sources on a Sunday push the table off the screen.
const SHOWN_AT_FIRST = 5

/** The line that stays when the block is folded: is anything wrong at all. */
function Summary({ health }: { health: Health }) {
  const share = health.polls ? (health.ok / health.polls) * 100 : null
  return (
    <p className="text-sm">
      <span className="font-semibold">Источники за сутки:</span>{' '}
      {health.polls === 0 ? (
        'опросов ещё не было'
      ) : (
        <>
          {formatNumber(health.polls)} {plural(health.polls, ['опрос', 'опроса', 'опросов'])},{' '}
          <span className={share !== null && share < 90 ? 'text-danger' : 'text-success'}>
            {shareOfGood(health.ok, health.polls)}% успешно
          </span>
        </>
      )}
      {health.failing.length > 0 && (
        <span className="text-danger"> · не читаются: {health.failing.length}</span>
      )}
      {health.silent.length > 0 && (
        <span className="text-muted"> · давно не публиковали: {health.silent.length}</span>
      )}
    </p>
  )
}

/** A list that shows its first rows and the rest on demand. */
function ShortList<T>({ items, render }: { items: T[]; render: (item: T) => ReactNode }) {
  const [isAll, setIsAll] = useState(false)
  const shown = isAll ? items : items.slice(0, SHOWN_AT_FIRST)
  return (
    <>
      <ul className="space-y-1 text-sm">{shown.map(render)}</ul>
      {items.length > SHOWN_AT_FIRST && (
        <button
          type="button"
          onClick={() => setIsAll((value) => !value)}
          className="mt-1.5 text-xs font-medium text-accent hover:underline"
        >
          {isAll ? 'Показать первые ' + SHOWN_AT_FIRST : `Показать все ${items.length}`}
        </button>
      )}
    </>
  )
}

function SectionTitle({ title, note }: { title: string; note: string }) {
  return (
    <div className="mb-1.5">
      <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">{title}</h3>
      <p className="text-xs text-muted">{note}</p>
    </div>
  )
}

/**
 * How the sources are doing: the share of good polls in a day, why the others
 * failed, the sources that fail and those silent longer than usual for them.
 * Every part says what it counts; the hints only add the details.
 */
export function SourceHealth() {
  const health = useSourceHealth()
  if (!health.data) return null
  const { errors, failing, silent, kinds } = health.data
  const kindOf = (kind: string | null) => kinds[kind ?? 'other'] ?? kind ?? kinds.other
  return (
    <Card className="mb-5 px-5 py-4">
      <Collapsible
        storageKey="source-health"
        title="состояние источников"
        head={<Summary health={health.data} />}
      >
        <div className="space-y-4 pt-3">
          {Object.keys(errors).length > 0 && (
            <section>
              <SectionTitle
                title="Почему опросы не прошли"
                note="Сколько раз за сутки опрос закончился ошибкой каждого рода."
              />
              <div className="flex flex-wrap gap-2">
                {Object.entries(errors).map(([kind, count]) => (
                  <Chip key={kind} tone="danger" hint={ERROR_HINTS[kind]}>
                    {kindOf(kind)} — {count} {plural(count, ['раз', 'раза', 'раз'])}
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {failing.length === 0 && silent.length === 0 && (
            <p className="text-sm text-muted">Все источники доступны и обновляются вовремя.</p>
          )}
          {failing.length > 0 && (
            <section>
              <SectionTitle
                title="Не читаются"
                note="Несколько опросов подряд закончились ошибкой. Текст ошибки — при наведении на строку."
              />
              <ShortList
                items={failing}
                render={(item) => (
                  <li
                    key={item.source_id}
                    title={item.error ?? undefined}
                    className={item.error ? 'cursor-help' : undefined}
                  >
                    <span className="font-medium">{item.name}</span>
                    <span className="text-muted">
                      {' '}
                      — {kindOf(item.kind)}: {item.failures}{' '}
                      {plural(item.failures, ['опрос', 'опроса', 'опросов'])} подряд с ошибкой
                      {item.since && `, последний удачный ${formatRelative(item.since)}`}
                    </span>
                    {item.error && (
                      <Help size={14} className="ml-1 inline align-[-2px] text-muted" />
                    )}
                  </li>
                )}
              />
            </section>
          )}
          {silent.length > 0 && (
            <section>
              <SectionTitle
                title="Давно не публиковали"
                note="Новых публикаций нет дольше, чем самая долгая пауза у источника за последний месяц."
              />
              <ShortList
                items={silent}
                render={(item) => (
                  <li key={item.source_id}>
                    <span className="font-medium">{item.name}</span>
                    <span className="text-muted">
                      {' '}
                      — последняя публикация {formatRelative(item.last_article)}, а за месяц пауза
                      не превышала{' '}
                      {item.longest_gap_hours < 1 ? 'часа' : pause(item.longest_gap_hours)}
                    </span>
                  </li>
                )}
              />
            </section>
          )}
        </div>
      </Collapsible>
    </Card>
  )
}
