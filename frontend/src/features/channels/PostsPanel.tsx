import clsx from 'clsx'
import { Check, ChevronDown, ExternalLink, PenLine, Send, Trash2 } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { ErrorBoundary } from '../../components/ErrorBoundary'
import { Button, Card, Chip, EmptyState, Spinner } from '../../components/ui'
import { DURATION, EASE, rowMotion } from '../../components/tokens'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import { formatDateTime } from '../../lib/format'
import { STATUS_LABEL } from '../../lib/publishing'
import type { Channel, Post } from '../../lib/publishing'
import { useDeletePost, usePosts, usePublishPost, useUpdatePost } from '../../lib/publishingQueries'
import { safeLink } from '../../lib/postText'
import { TelegramPreview } from './TelegramPreview'

// The editor brings ProseMirror along: it loads when a post is opened for editing.
const PostEditor = lazy(() => import('./PostEditor').then((m) => ({ default: m.PostEditor })))

const TONE: Record<Post['status'], 'neutral' | 'accent' | 'spark' | 'ok' | 'danger'> = {
  composing: 'accent',
  draft: 'spark',
  queued: 'accent',
  sending: 'accent',
  sent: 'ok',
  failed: 'danger',
  skipped: 'neutral',
}

const FOLDED_HEIGHT = 360
// Folding a post that is only a little longer would hide two lines behind a button.
const FOLD_MARGIN = 80

/** A long post folded to its first screen and unfolded on demand. */
function Folded({ children }: { children: ReactNode }) {
  const inner = useRef<HTMLDivElement>(null)
  const [isOpen, setOpen] = useState(false)
  const [isLong, setLong] = useState(false)
  useEffect(() => {
    const node = inner.current
    if (!node) return
    const observer = new ResizeObserver(() =>
      setLong(node.offsetHeight > FOLDED_HEIGHT + FOLD_MARGIN),
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  const isFolded = isLong && !isOpen
  return (
    <div>
      <motion.div
        initial={false}
        animate={{ height: isFolded ? FOLDED_HEIGHT : 'auto' }}
        transition={{ duration: DURATION.medium, ease: EASE }}
        className="overflow-hidden"
        style={
          isFolded ? { maskImage: 'linear-gradient(to bottom, black 70%, transparent)' } : undefined
        }
      >
        <div ref={inner}>{children}</div>
      </motion.div>
      {isLong && (
        <button
          type="button"
          onClick={() => setOpen((open) => !open)}
          aria-expanded={isOpen}
          className="state-layer relative mt-1 inline-flex h-8 items-center gap-1 overflow-hidden rounded-full px-3 text-[13px] font-medium text-primary"
        >
          <ChevronDown
            size={15}
            className={clsx('transition-transform duration-300', isOpen && 'rotate-180')}
          />
          {isOpen ? 'Свернуть' : 'Показать целиком'}
        </button>
      )}
    </div>
  )
}

function when(post: Post): string {
  if (post.sent_at) return `опубликован ${formatDateTime(post.sent_at)}`
  if (post.slot_at) return `на ${formatDateTime(post.slot_at)}`
  return `создан ${formatDateTime(post.created_at)}`
}

function PostRow({
  post,
  channel,
  index,
}: {
  post: Post
  channel: Channel | undefined
  index: number
}) {
  const publish = usePublishPost()
  const remove = useDeletePost()
  const approve = useUpdatePost()
  const update = useUpdatePost()
  const [editing, setEditing] = useState(false)
  const canEdit = ['draft', 'queued', 'failed'].includes(post.status) && post.content
  const title = channel?.title ?? 'Канал'

  return (
    <motion.li {...rowMotion(index)} exit={{ opacity: 0, x: -20 }} layout="position">
      <Card variant="outlined" className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-outline-variant px-4 py-3">
          <Chip tone={TONE[post.status]}>
            {(post.status === 'composing' || post.status === 'sending') && (
              <Spinner className="size-3" />
            )}
            {STATUS_LABEL[post.status]}
          </Chip>
          <span className="text-sm font-medium">{title}</span>
          <span className="text-xs text-outline">· {when(post)}</span>
          {post.kind === 'digest' && <Chip tone="accent">обзор</Chip>}
          <span className="ml-auto flex flex-wrap gap-1">
            {post.message_url && (
              <a
                href={safeLink(post.message_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="state-layer relative inline-flex h-8 items-center gap-1.5 overflow-hidden rounded-full px-3 text-[13px] font-medium text-primary"
              >
                <ExternalLink size={14} /> В Telegram
              </a>
            )}
            {canEdit && (
              <Button
                size="sm"
                variant="ghost"
                icon={<PenLine size={14} />}
                onClick={() => setEditing(true)}
              >
                Править
              </Button>
            )}
            {post.status === 'draft' && (
              <Button
                size="sm"
                variant="tonal"
                icon={<Check size={14} />}
                isBusy={approve.isPending}
                onClick={() =>
                  approve.mutate(
                    { id: post.id, approve: true },
                    { onSuccess: () => toast.success('Пост в очереди') },
                  )
                }
              >
                Одобрить
              </Button>
            )}
            {canEdit && (
              <Button
                size="sm"
                variant="primary"
                icon={<Send size={14} />}
                isBusy={publish.isPending}
                onClick={() =>
                  publish.mutate(post.id, {
                    onSuccess: () => toast.success('Отправляем'),
                  })
                }
              >
                Сейчас
              </Button>
            )}
            {!['sent', 'sending'].includes(post.status) && (
              <Button
                size="sm"
                variant="danger"
                aria-label="Убрать пост"
                icon={<Trash2 size={14} />}
                onClick={() => remove.mutate(post.id)}
              />
            )}
          </span>
        </div>
        <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
          <div className="min-w-0 space-y-2 text-sm">
            {post.articles.map((article) => (
              <a
                key={article.id}
                href={safeLink(article.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="block line-clamp-2 text-on-surface-variant hover:text-primary"
              >
                {article.source} · {article.title}
              </a>
            ))}
            {post.error && (
              <p
                className={clsx(
                  'rounded-xl px-3 py-2 text-xs',
                  post.status === 'failed'
                    ? 'bg-error-container text-on-error-container'
                    : 'bg-surface-container text-on-surface-variant',
                )}
              >
                {post.error}
              </p>
            )}
            {post.problems.map((problem) => (
              <p key={problem} className="text-xs text-destructive">
                {problem}
              </p>
            ))}
            {post.status === 'composing' && (
              <div className="space-y-2 pt-1" aria-label="Пост пишется">
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-2/3" />
              </div>
            )}
          </div>
          {post.content && (
            <Folded>
              <TelegramPreview content={post.content} channel={title} />
            </Folded>
          )}
        </div>
      </Card>

      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto rounded-[28px] sm:max-w-6xl">
          <DialogHeader>
            <DialogTitle>Пост для «{title}»</DialogTitle>
            <DialogDescription>
              Форматирование, картинки и кнопки как в редакторе Telegram.
            </DialogDescription>
          </DialogHeader>
          {post.content && (
            <ErrorBoundary title="Редактор не загрузился">
              <Suspense
                fallback={
                  <div className="grid h-80 place-items-center">
                    <Spinner className="size-8 text-primary" label="Открываем редактор" />
                  </div>
                }
              >
                <PostEditor
                  initial={post.content}
                  channel={title}
                  isBusy={update.isPending}
                  onCancel={() => setEditing(false)}
                  onSave={(content, approve) =>
                    update.mutate(
                      { id: post.id, content, approve },
                      {
                        onSuccess: () => {
                          toast.success(approve ? 'Сохранено и в очереди' : 'Черновик сохранён')
                          setEditing(false)
                        },
                      },
                    )
                  }
                />
              </Suspense>
            </ErrorBoundary>
          )}
        </DialogContent>
      </Dialog>
    </motion.li>
  )
}

/** Queue and history: what is being written, waits, went out or failed. */
export function PostsPanel({ channelId, channels }: { channelId?: string; channels: Channel[] }) {
  const { data: posts, isPending } = usePosts(channelId)
  const byId = new Map(channels.map((channel) => [channel.id, channel]))
  if (isPending) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-48" />
        <div className="skeleton h-48" />
      </div>
    )
  }
  if (!posts?.length) {
    return (
      <Card variant="outlined">
        <EmptyState icon={<Send size={22} />} title="Постов пока нет">
          Нажмите «Пост сейчас» или «Черновик» у канала, или дождитесь расписания.
        </EmptyState>
      </Card>
    )
  }
  return (
    <ul className="space-y-3">
      <AnimatePresence initial={false}>
        {posts.map((post, index) => (
          <PostRow key={post.id} post={post} channel={byId.get(post.channel_id)} index={index} />
        ))}
      </AnimatePresence>
    </ul>
  )
}
