import clsx from 'clsx'
import { Plus, RefreshCw, Search, Send, Trash2 } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { Segmented } from '../../components/Segmented'
import { EASE, INPUT_CLASS } from '../../components/tokens'
import { Button, Card, Chip, ErrorNote, Field, Toggle } from '../../components/ui'
import type { Source, SourceCategory, SourceCreate } from '../../lib/api'
import { CATEGORY_LABELS, externalHref, formatNumber, formatRelative } from '../../lib/format'
import { useSourceMutations } from '../../lib/queries'
import {
  CATEGORY_ORDER,
  KIND_LABELS,
  groupSources,
  isProtected,
  matchesSource,
  queryWords,
  readVia,
} from '../../lib/sourceList'
import type { SourceGrouping, SourceOrder } from '../../lib/sourceList'
import { SourceAvatar } from '../feed/SourceAvatar'
import { DetectSourceForm } from './DetectSourceForm'

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
        !source.enabled && 'bg-outline-variant',
        source.enabled && failing && 'bg-destructive',
        source.enabled && !failing && (never ? 'bg-outline' : 'bg-success'),
      )}
    />
  )
}

// Any address first: the worker tells what it is. A feed or a channel by hand
// stays for those who know what they have.
const MODES = [
  { value: 'any', label: 'Любой адрес', short: 'Адрес' },
  { value: 'rss', label: 'Лента RSS или Atom', short: 'RSS' },
  { value: 'telegram', label: 'Telegram-канал', short: 'Telegram' },
] as const
type AddMode = (typeof MODES)[number]['value']

type SourceForm = {
  kind: 'rss' | 'telegram'
  name: string
  /** The feed's address, or the channel: "@name" or its t.me link. */
  address: string
  category: SourceCategory
  language: 'ru' | 'en'
  fetch_full_text: boolean
}

function toRequest(form: SourceForm): SourceCreate {
  const { kind, name, address, ...common } = form
  return kind === 'telegram'
    ? { ...common, kind, channel: address.trim(), ...(name.trim() ? { name: name.trim() } : {}) }
    : { ...common, kind, name: name.trim(), feed_url: address.trim() }
}

/** Articles stored from the source, and how many came in a day. */
function ArticleCount({ source }: { source: Source }) {
  return (
    <>
      <span title="Публикаций всего">{formatNumber(source.articles)}</span>
      {source.articles_last_day > 0 && (
        <span className="ml-1.5 text-success" title="Публикаций за последние сутки">
          +{source.articles_last_day}
          <span className="sr-only"> за сутки</span>
        </span>
      )}
    </>
  )
}

function AddSourceForm({ onDone, onAdded }: { onDone: () => void; onAdded: () => void }) {
  const { create } = useSourceMutations()
  const [mode, setMode] = useState<AddMode>('any')
  const [form, setForm] = useState<SourceForm>({
    kind: 'rss',
    name: '',
    address: '',
    category: 'security',
    language: 'ru',
    fetch_full_text: false,
  })
  const isChannel = form.kind === 'telegram'
  const termsId = useId()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate(toRequest(form), {
      onSuccess: () => {
        onAdded()
        onDone()
      },
    })
  }

  const modes = (
    <Segmented
      label="Что добавить"
      value={mode}
      options={MODES}
      // An address of one kind means nothing to the other. A channel's short
      // posts mostly point to articles, which are worth opening.
      onChange={(next) => {
        setMode(next)
        if (next !== 'any') {
          setForm({ ...form, kind: next, address: '', fetch_full_text: next === 'telegram' })
        }
      }}
      className="sm:max-w-lg"
    />
  )
  if (mode === 'any') {
    return (
      <div className="border-b border-outline-variant">
        <div className="px-5 pt-5">{modes}</div>
        <DetectSourceForm onDone={onDone} onAdded={onAdded} />
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4 border-b border-outline-variant p-5">
      {modes}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название" hint={isChannel ? 'необязательно' : undefined}>
          <input
            required={!isChannel}
            minLength={2}
            placeholder={isChannel ? 'по умолчанию из канала' : undefined}
            className={INPUT_CLASS}
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label={isChannel ? 'Канал' : 'Адрес RSS или Atom'}>
          <input
            required
            type={isChannel ? 'text' : 'url'}
            placeholder={isChannel ? '@channel или t.me/channel' : 'https://example.org/feed.xml'}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            aria-describedby={isChannel ? termsId : undefined}
            className={INPUT_CLASS}
            value={form.address}
            onChange={(event) => setForm({ ...form, address: event.target.value })}
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
      <label className="flex items-center gap-2.5 text-sm text-muted-foreground">
        <Toggle
          label="Загружать полный текст"
          checked={form.fetch_full_text}
          onChange={(fetch_full_text) => setForm({ ...form, fetch_full_text })}
        />
        {isChannel
          ? 'Открывать статьи, на которые ведут короткие посты'
          : 'Загружать полный текст статей (если в ленте только анонс)'}
      </label>
      {isChannel && (
        <p id={termsId} className="max-w-2xl text-xs leading-relaxed text-outline">
          Канал читается через открытую страницу t.me/s/канал, без аккаунта. Каналы с закрытым
          веб-превью так не прочитать. Условия Telegram запрещают брать посты для ИИ без согласия
          владельца, поэтому добавляйте каналы, авторы которых не против.
        </p>
      )}
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

const GROUPINGS = [
  { value: 'category', label: 'По темам', short: 'Темы' },
  { value: 'kind', label: 'Сайты и Telegram', short: 'Откуда' },
] as const satisfies readonly { value: SourceGrouping; label: string; short: string }[]

const ORDERS = [
  { value: 'name', label: 'По названию', short: 'А-Я' },
  { value: 'most', label: 'Больше новостей', short: 'Больше' },
  { value: 'least', label: 'Меньше новостей', short: 'Меньше' },
] as const satisfies readonly { value: SourceOrder; label: string; short: string }[]

const SHOWN = [
  { value: 'all', label: 'Все', short: 'Все' },
  { value: 'protected', label: 'Защищённые', short: 'Защищ.' },
] as const

type Props = {
  sources: Source[]
  /** Polls the whole catalogue at once. */
  isAdmin: boolean
  /** May add sources: an administrator, or anyone in an open catalogue. */
  canAdd: boolean
}

/** How a source is read, where it is not a plain feed or a plain request. */
function ReadBadges({ source }: { source: Source }) {
  const kind = KIND_LABELS[source.kind]
  const via = readVia(source)
  return (
    <>
      {kind && <Chip className="max-sm:hidden">{kind}</Chip>}
      {via && (
        <Chip tone="spark" title={via.note ?? undefined} className="max-sm:hidden">
          {via.label}
        </Chip>
      )}
    </>
  )
}

export function SourcesTable({ sources, isAdmin, canAdd }: Props) {
  const { toggle, remove, refreshOne, refreshAll } = useSourceMutations()
  const [adding, setAdding] = useState(false)
  // In the address, so a search survives a reload and can be sent on.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const isSearching = queryWords(query).length > 0
  // Sites that refuse a bot and are read a step up the ladder or through a proxy.
  const shown = params.get('show') === 'protected' ? 'protected' : 'all'
  const found = sources.filter(
    (source) => matchesSource(source, query) && (shown === 'all' || isProtected(source)),
  )
  const searchBox = useRef<HTMLInputElement>(null)
  const grouping: SourceGrouping = params.get('group') === 'kind' ? 'kind' : 'category'
  const order = ORDERS.find((item) => item.value === params.get('order'))?.value ?? 'name'
  const groups = groupSources(found, grouping, order)
  // An empty value leaves the address, so the defaults keep it clean.
  const setParam = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value) next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  const setQuery = (value: string) => setParam('q', value)

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant px-5 py-3.5">
        <p className="text-sm text-muted-foreground">
          {isSearching ? (
            <>
              Найдено <span className="font-semibold text-foreground">{found.length}</span> из{' '}
              {sources.length}
            </>
          ) : (
            <>
              <span className="font-semibold text-foreground">
                {sources.filter((s) => s.enabled).length}
              </span>{' '}
              из {sources.length} источников включено · опрос каждые 15 минут
            </>
          )}
          <span className="mt-0.5 block text-xs text-outline">
            Число у источника - публикаций всего, <span className="text-success">+N</span> за сутки.
            {!isAdmin &&
              (canAdd
                ? ' Добавить можно любой сайт или канал; свои источники вы отключаете и удаляете сами.'
                : ' Включает и отключает источники администратор.')}
          </span>
        </p>
        <div className={clsx('flex gap-2', !canAdd && 'hidden')}>
          <Button
            size="sm"
            className={clsx(!isAdmin && 'hidden')}
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

      <div className="border-b border-outline-variant px-5 py-3">
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-outline"
          />
          <input
            type="search"
            aria-label="Поиск по источникам"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            ref={searchBox}
            placeholder="Название, адрес или @канал"
            className="w-full rounded-lg border border-outline-variant bg-card py-2.5 pr-3 pl-9 text-sm placeholder:text-outline hover:border-outline focus:border-primary focus:outline-none"
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
          <Segmented
            label="Группировать"
            value={grouping}
            options={GROUPINGS}
            onChange={(value) => setParam('group', value === 'category' ? '' : value)}
          />
          <Segmented
            label="Порядок"
            value={order}
            options={ORDERS}
            onChange={(value) => setParam('order', value === 'name' ? '' : value)}
          />
          <Segmented
            label="Показать"
            value={shown}
            options={SHOWN}
            onChange={(value) => setParam('show', value === 'all' ? '' : value)}
          />
        </div>
        {/* Read out only while searching, and only the count. */}
        <p className="sr-only" aria-live="polite">
          {isSearching ? `Найдено ${found.length} из ${sources.length}` : ''}
        </p>
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
            {/* A new source must not hide behind a search it does not match. */}
            <AddSourceForm onDone={() => setAdding(false)} onAdded={() => setQuery('')} />
          </motion.div>
        )}
      </AnimatePresence>

      {isSearching && found.length === 0 && (
        <p className="px-5 py-10 text-center text-sm break-words text-muted-foreground">
          Нет источников по запросу «{query.trim()}».{' '}
          <button
            type="button"
            onClick={() => {
              setQuery('')
              // The button goes away with the empty list; the search box keeps the focus.
              searchBox.current?.focus()
            }}
            className="font-medium text-primary hover:underline"
          >
            Сбросить поиск
          </button>
        </p>
      )}

      {groups.map((group) => (
        <section key={group.key}>
          <h3 className="flex justify-between bg-surface-container px-5 py-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {group.label}
            <span className="tabular font-normal normal-case">{group.sources.length}</span>
          </h3>
          <ul className="divide-y divide-outline-variant">
            {group.sources.map((source) => (
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
                    className="flex items-center gap-1.5 text-sm font-medium hover:text-on-primary-container"
                  >
                    <SourceAvatar
                      sourceId={source.id}
                      name={source.name}
                      className="size-6 text-[10px]"
                    />
                    {source.kind === 'telegram' && (
                      <Send
                        size={14}
                        aria-label="Telegram-канал"
                        className="shrink-0 text-outline"
                      />
                    )}
                    <span className="truncate">{source.name}</span>
                  </a>
                  <p className="truncate text-xs text-outline">
                    {/* On a phone the count moves here, under the name. */}
                    <span className="tabular sm:hidden">
                      <ArticleCount source={source} />
                      {' · '}
                    </span>
                    {source.last_status === 'error'
                      ? (source.last_error ?? 'ошибка опроса')
                      : source.last_fetched_at
                        ? `опрошен ${formatRelative(source.last_fetched_at)}`
                        : 'ещё не опрашивался'}
                  </p>
                </div>
                {/* On a phone the name needs the room more than these do. */}
                <ReadBadges source={source} />
                <Chip className="max-sm:hidden">{source.language.toUpperCase()}</Chip>
                <span className="tabular w-24 shrink-0 text-right text-xs text-muted-foreground max-sm:hidden">
                  <ArticleCount source={source} />
                </span>
                <div
                  className={clsx(
                    // Shown on hover with a mouse; a touch screen has no hover, so there they stay.
                    'flex items-center gap-0.5 transition-opacity pointer-fine:opacity-0 pointer-fine:group-focus-within:opacity-100 pointer-fine:group-hover:opacity-100',
                    !source.can_edit && 'hidden',
                  )}
                >
                  <button
                    type="button"
                    aria-label="Опросить источник"
                    onClick={() => refreshOne.mutate(source.id)}
                    className="grid size-7 place-items-center rounded-md text-outline hover:bg-surface-container hover:text-foreground"
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
                    className="grid size-7 place-items-center rounded-md text-outline hover:bg-error-container hover:text-destructive"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                {source.can_edit ? (
                  <Toggle
                    label={`${source.enabled ? 'Отключить' : 'Включить'} ${source.name}`}
                    checked={source.enabled}
                    onChange={(enabled) => toggle.mutate({ id: source.id, enabled })}
                  />
                ) : (
                  // A switch that cannot be switched only puzzles: an off source says so in words.
                  !source.enabled && <span className="shrink-0 text-xs text-outline">выключен</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </Card>
  )
}
