import clsx from 'clsx'
import { Plus, RefreshCw, Trash2 } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { EASE, INPUT_CLASS } from '../../components/tokens'
import { Button, Card, Chip, ErrorNote, Field, Toggle } from '../../components/ui'
import type { Source, SourceCategory, SourceCreate } from '../../lib/api'
import { CATEGORY_LABELS, externalHref, formatNumber, formatRelative } from '../../lib/format'
import { useSourceMutations } from '../../lib/queries'

const CATEGORY_ORDER: SourceCategory[] = ['security', 'ics', 'energy', 'it', 'regulator']

function StatusDot({ source }: { source: Source }) {
  const failing = source.last_status === 'error'
  const never = source.last_fetched_at === null
  const title = failing
    ? `Ошибка: ${source.last_error ?? 'неизвестна'}`
    : never
      ? 'Ещё не опрашивался'
      : `Опрошен ${formatRelative(source.last_fetched_at as string)}`
  // The colour repeats what the line under the source name says in words.
  return (
    <span
      role="img"
      title={title}
      aria-label={source.enabled ? title : 'Источник отключён'}
      className={clsx(
        'size-2 shrink-0 rounded-full',
        !source.enabled && 'bg-line',
        source.enabled && failing && 'bg-danger',
        source.enabled && !failing && (never ? 'bg-faint' : 'bg-ok'),
      )}
    />
  )
}

function AddSourceForm({ onDone }: { onDone: () => void }) {
  const { create } = useSourceMutations()
  const [form, setForm] = useState<SourceCreate>({
    name: '',
    feed_url: '',
    category: 'security',
    language: 'ru',
    fetch_full_text: false,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate(form, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="space-y-4 border-b border-line p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название">
          <input
            required
            minLength={2}
            className={INPUT_CLASS}
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label="Адрес RSS или Atom">
          <input
            required
            type="url"
            placeholder="https://example.org/feed.xml"
            className={INPUT_CLASS}
            value={form.feed_url}
            onChange={(event) => setForm({ ...form, feed_url: event.target.value })}
          />
        </Field>
        <Field label="Категория">
          <select
            className={INPUT_CLASS}
            value={form.category}
            onChange={(event) =>
              setForm({ ...form, category: event.target.value as SourceCategory })
            }
          >
            {CATEGORY_ORDER.map((category) => (
              <option key={category} value={category}>
                {CATEGORY_LABELS[category]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Язык">
          <select
            className={INPUT_CLASS}
            value={form.language}
            onChange={(event) => setForm({ ...form, language: event.target.value as 'ru' | 'en' })}
          >
            <option value="ru">Русский</option>
            <option value="en">Английский</option>
          </select>
        </Field>
      </div>
      <label className="flex items-center gap-2.5 text-sm text-muted">
        <Toggle
          label="Загружать полный текст"
          checked={form.fetch_full_text}
          onChange={(fetch_full_text) => setForm({ ...form, fetch_full_text })}
        />
        Загружать полный текст статей (если в ленте только анонс)
      </label>
      <ErrorNote error={create.error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" isBusy={create.isPending}>
          Добавить и опросить
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Отмена
        </Button>
      </div>
    </form>
  )
}

type Props = {
  sources: Source[]
  /** The catalogue is shared; only an administrator may change it. */
  canEdit: boolean
}

export function SourcesTable({ sources, canEdit }: Props) {
  const { toggle, remove, refreshOne, refreshAll } = useSourceMutations()
  const [adding, setAdding] = useState(false)

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
        <p className="text-sm text-muted">
          <span className="font-semibold text-text">{sources.filter((s) => s.enabled).length}</span>{' '}
          из {sources.length} источников включено · опрос каждые 15 минут
        </p>
        <div className={clsx('flex gap-2', !canEdit && 'hidden')}>
          <Button
            size="sm"
            icon={<RefreshCw size={14} className={clsx(refreshAll.isPending && 'animate-spin')} />}
            onClick={() =>
              refreshAll.mutate(undefined, {
                // Show the confirmation briefly, then return to the normal label.
                onSuccess: () => setTimeout(() => refreshAll.reset(), 4000),
              })
            }
          >
            {refreshAll.isSuccess ? 'Опрос запущен' : 'Опросить сейчас'}
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Plus size={15} />}
            onClick={() => setAdding(true)}
          >
            Источник
          </Button>
        </div>
      </div>

      <ErrorNote error={toggle.error ?? remove.error ?? refreshOne.error ?? refreshAll.error} />

      <AnimatePresence initial={false}>
        {adding && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: EASE }}
            className="overflow-hidden"
          >
            <AddSourceForm onDone={() => setAdding(false)} />
          </motion.div>
        )}
      </AnimatePresence>

      {CATEGORY_ORDER.map((category) => {
        const group = sources.filter((source) => source.category === category)
        if (group.length === 0) return null
        return (
          <section key={category}>
            <h3 className="bg-sunken px-5 py-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
              {CATEGORY_LABELS[category]}
            </h3>
            <ul className="divide-y divide-line">
              {group.map((source) => (
                <li
                  key={source.id}
                  className={clsx(
                    'group flex items-center gap-3 px-5 py-2.5 transition-opacity',
                    !source.enabled && 'opacity-55',
                  )}
                >
                  <StatusDot source={source} />
                  <div className="min-w-0 flex-1">
                    <a
                      href={externalHref(source.site_url ?? source.feed_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate text-sm font-medium hover:text-accent-text"
                    >
                      {source.name}
                    </a>
                    <p className="truncate text-xs text-faint">
                      {source.last_status === 'error'
                        ? (source.last_error ?? 'ошибка опроса')
                        : source.last_fetched_at
                          ? `опрошен ${formatRelative(source.last_fetched_at)}`
                          : 'ещё не опрашивался'}
                    </p>
                  </div>
                  <Chip>{source.language.toUpperCase()}</Chip>
                  <span className="tabular w-24 text-right text-xs text-muted">
                    {formatNumber(source.articles)}
                    {source.articles_last_day > 0 && (
                      <span className="ml-1.5 text-ok">+{source.articles_last_day}</span>
                    )}
                  </span>
                  <div
                    className={clsx(
                      'flex items-center gap-0.5 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100',
                      !canEdit && 'hidden',
                    )}
                  >
                    <button
                      type="button"
                      aria-label="Опросить источник"
                      onClick={() => refreshOne.mutate(source.id)}
                      className="grid size-7 place-items-center rounded-md text-faint hover:bg-sunken hover:text-text"
                    >
                      <RefreshCw size={13} />
                    </button>
                    <button
                      type="button"
                      aria-label="Удалить источник"
                      onClick={() => {
                        if (window.confirm(`Удалить «${source.name}» вместе с его публикациями?`)) {
                          remove.mutate(source.id)
                        }
                      }}
                      className="grid size-7 place-items-center rounded-md text-faint hover:bg-danger-soft hover:text-danger"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  <Toggle
                    label={`${source.enabled ? 'Отключить' : 'Включить'} ${source.name}`}
                    checked={source.enabled}
                    disabled={!canEdit}
                    onChange={(enabled) => toggle.mutate({ id: source.id, enabled })}
                  />
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </Card>
  )
}
