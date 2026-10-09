import clsx from 'clsx'
import { CircleAlert, Trash2, EventRepeat } from '../../components/icons'
import { AnimatePresence, LayoutGroup, motion } from 'motion/react'
import { MorphingTitle } from './DigestHeading'
import { Spinner } from '../../components/ui'
import type { DigestSummary } from '../../lib/api'
import { formatPeriod, formatRelative, plural } from '../../lib/format'

type Props = {
  digests: DigestSummary[]
  activeId?: string
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

function statusLine(digest: DigestSummary): string {
  if (digest.status === 'done') {
    const selected = digest.stats.selected ?? 0
    const noun = plural(selected, ['публикация', 'публикации', 'публикаций'])
    return `${selected} ${noun} · ${formatPeriod(digest.period_start, digest.period_end)}`
  }
  return digest.status === 'failed' ? 'не удалось собрать' : 'собирается'
}

export function History({ digests, activeId, onSelect, onDelete }: Props) {
  if (digests.length === 0) {
    return <p className="px-1 text-sm text-muted">Здесь появятся собранные выпуски.</p>
  }
  return (
    <LayoutGroup id="digest-history">
      <ul className="space-y-1.5">
        <AnimatePresence initial={false}>
          {digests.map((digest) => {
            const isActive = digest.id === activeId
            const isRunning = digest.status === 'queued' || digest.status === 'running'
            const name = digest.title ?? digest.profile_name
            return (
              <motion.li
                key={digest.id}
                layout="position"
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="group relative"
              >
                <button
                  type="button"
                  onClick={() => onSelect(digest.id)}
                  aria-current={isActive}
                  className={clsx(
                    'relative isolate w-full rounded-2xl px-3 py-2.5 pr-9 text-left transition-colors duration-300',
                    isActive ? 'text-foreground' : 'hover:bg-default/60',
                  )}
                >
                  {/* One highlight for the list: it flows to the row that opens. */}
                  {isActive && (
                    <motion.span
                      layoutId="history-highlight"
                      className="absolute inset-0 -z-10 bg-surface shadow-surface ring-1 ring-border"
                      style={{ borderRadius: 16 }}
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                    />
                  )}
                  {isActive ? (
                    <span className="line-clamp-2 text-[13px] leading-snug font-semibold">
                      {name}
                    </span>
                  ) : (
                    // The open digest's title is in the page header; every other
                    // row's title can grow into it.
                    <MorphingTitle digestId={digest.id}>
                      <span className="line-clamp-2 text-[13px] leading-snug font-medium">
                        {name}
                      </span>
                    </MorphingTitle>
                  )}
                  {/* On the highlight the lines take its text colour, a shade lighter. */}
                  <span
                    className={clsx(
                      'mt-1 flex items-center gap-1.5 text-xs',
                      isActive ? 'opacity-85' : 'text-muted',
                    )}
                  >
                    {isRunning && (
                      <Spinner
                        className={clsx('size-3 border-[1.5px]', !isActive && 'text-accent')}
                      />
                    )}
                    {digest.status === 'failed' && (
                      <CircleAlert size={12} className="text-danger" />
                    )}
                    <span className="truncate">{statusLine(digest)}</span>
                  </span>
                  <span
                    className={clsx(
                      'mt-0.5 flex items-center gap-1 truncate text-[11px]',
                      isActive ? 'opacity-70' : 'text-muted',
                    )}
                  >
                    {digest.origin === 'schedule' && (
                      <EventRepeat
                        size={12}
                        className="shrink-0"
                        aria-label="собран по расписанию"
                      />
                    )}
                    <span className="truncate">
                      {digest.profile_name}
                      {/* Two digests of one profile, one for each audience, tell apart here. */}
                      {digest.audience === 'management' ? ' · руководству' : ''} ·{' '}
                      {formatRelative(digest.created_at)}
                    </span>
                  </span>
                </button>
                {!isRunning && (
                  <button
                    type="button"
                    aria-label={`Удалить выпуск «${name}»`}
                    onClick={() => {
                      if (window.confirm(`Удалить выпуск «${name}»?`)) onDelete(digest.id)
                    }}
                    // Always visible on touch screens, where there is no hover.
                    className={clsx(
                      'absolute top-2 right-2 grid size-6 place-items-center rounded-md transition-opacity',
                      'text-muted',
                      'hover:bg-danger-soft hover:text-danger focus-visible:opacity-100 pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100',
                    )}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
    </LayoutGroup>
  )
}
