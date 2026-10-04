import { useState } from 'react'
import type { FormEvent } from 'react'
import { SelectField } from '../../components/SelectField'
import { INPUT_CLASS } from '../../components/tokens'
import { Button, Chip, ErrorNote, Field } from '../../components/ui'
import type { DetectedSource, SourceCategory, SourceCreate } from '../../lib/api'
import { CATEGORY_LABELS, externalHref, formatDate } from '../../lib/format'
import { useSourceDetection, useSourceMutations } from '../../lib/queries'
import { CATEGORY_ORDER, readVia } from '../../lib/sourceList'

const FOUND_LABELS: Record<DetectedSource['kind'], string> = {
  rss: 'Лента RSS или Atom',
  telegram: 'Telegram-канал',
  page: 'Веб-страница без RSS',
  wordpress: 'WordPress API',
}

/** The request that adds what the worker found, as it found it. */
function toRequest(found: DetectedSource, name: string, category: SourceCategory): SourceCreate {
  const language = found.language === 'en' ? 'en' : 'ru'
  if (found.kind === 'telegram') {
    // A channel's short posts mostly point to articles, which are worth opening.
    return {
      kind: 'telegram',
      channel: found.address,
      name,
      category,
      language,
      fetch_full_text: true,
    }
  }
  if (found.kind === 'rss') {
    return {
      kind: 'rss',
      name,
      feed_url: found.address,
      category,
      language,
      fetch_full_text: false,
    }
  }
  return {
    kind: found.kind,
    name,
    feed_url: found.address,
    ...(found.site_url ? { site_url: found.site_url } : {}),
    ...(found.link_selector ? { link_selector: found.link_selector } : {}),
    category,
    language,
    fetch_full_text: false,
  }
}

type Props = { onDone: () => void; onAdded: () => void }

/**
 * Any address: a site, its news section, a feed or a channel. The worker
 * tells what it is, how it reads it and which articles it sees, before
 * anything is saved.
 */
export function DetectSourceForm({ onDone, onAdded }: Props) {
  const { start, result } = useSourceDetection()
  const { create } = useSourceMutations()
  const [address, setAddress] = useState('')
  const [selector, setSelector] = useState('')
  const [isSelectorShown, setIsSelectorShown] = useState(false)
  const [name, setName] = useState<string | null>(null)
  const [category, setCategory] = useState<SourceCategory>('security')

  const answer = result.data?.status === 'done' ? result.data : null
  const found = answer?.found ?? null
  const isChecking = start.isPending || (Boolean(start.data) && answer === null && !result.isError)
  const via = found ? readVia(found) : null

  const check = (event: FormEvent) => {
    event.preventDefault()
    setName(null)
    create.reset()
    start.mutate({ address: address.trim(), linkSelector: selector.trim() || undefined })
  }

  const add = () => {
    if (!found) return
    create.mutate(toRequest(found, (name ?? found.name).trim(), category), {
      onSuccess: () => {
        onAdded()
        onDone()
      },
    })
  }

  return (
    <div className="space-y-4 p-5">
      <form onSubmit={check} className="space-y-3">
        <Field label="Адрес" hint="URL сайта, RSS-лента или @канал">
          <div className="flex gap-2">
            <input
              required
              minLength={3}
              placeholder="https://example.org/news или @channel"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              className={INPUT_CLASS}
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
            <Button type="submit" variant="primary" isBusy={isChecking}>
              Проверить
            </Button>
          </div>
        </Field>
        {isSelectorShown ? (
          <Field label="CSS-селектор ссылок" hint="если ссылки не найдены автоматически">
            <input
              placeholder="article h2 a"
              autoComplete="off"
              spellCheck={false}
              className={INPUT_CLASS}
              value={selector}
              onChange={(event) => setSelector(event.target.value)}
            />
          </Field>
        ) : (
          <button
            type="button"
            onClick={() => setIsSelectorShown(true)}
            className="text-xs font-medium text-primary hover:underline"
          >
            Указать селектор ссылок
          </button>
        )}
      </form>

      {isChecking && (
        <p className="text-sm text-muted-foreground" role="status">
          Ищем RSS-ленту, новости и статьи. Если сайт блокирует бота, откроем его в браузере: это
          займёт до минуты.
        </p>
      )}
      <ErrorNote error={start.error ?? result.error} />
      {answer?.error && (
        <p className="text-sm text-destructive" role="alert">
          {answer.error}
        </p>
      )}

      {found && (
        <div className="space-y-3 rounded-xl bg-surface-container p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="accent">{FOUND_LABELS[found.kind]}</Chip>
            {via && (
              <Chip tone="spark" title={via.note ?? undefined}>
                {via.label}
              </Chip>
            )}
            <span className="min-w-0 truncate text-xs text-outline">{found.address}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Название">
              <input
                required
                minLength={2}
                className={INPUT_CLASS}
                value={name ?? found.name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
            <Field label="Категория">
              <SelectField
                label="Категория"
                value={category}
                onChange={(value) => setCategory(value as SourceCategory)}
                options={CATEGORY_ORDER.map((item) => ({
                  value: item,
                  label: CATEGORY_LABELS[item],
                }))}
              />
            </Field>
          </div>
          {found.samples.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Последние статьи</p>
              <ul className="space-y-1 text-sm">
                {found.samples.map((sample) => (
                  <li key={sample.url} className="flex gap-2">
                    {sample.published_at && (
                      <span className="tabular shrink-0 text-xs text-outline">
                        {formatDate(sample.published_at)}
                      </span>
                    )}
                    <a
                      href={externalHref(sample.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-w-0 truncate hover:text-on-primary-container"
                    >
                      {sample.title || sample.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ErrorNote error={create.error} />
          <div className="flex gap-2">
            <Button variant="primary" isBusy={create.isPending} onClick={add}>
              Добавить и опросить
            </Button>
            <Button variant="ghost" onClick={onDone}>
              Отмена
            </Button>
          </div>
        </div>
      )}
      {!found && (
        <Button variant="ghost" onClick={onDone}>
          Отмена
        </Button>
      )}
    </div>
  )
}
