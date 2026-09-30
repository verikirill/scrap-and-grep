import clsx from 'clsx'
import { Captions, Check, Clapperboard, Download, Mic, RotateCcw } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { buttonClass, EASE } from '../../components/tokens'
import { Button, Card, ErrorNote } from '../../components/ui'
import type { Video, VideoStage } from '../../lib/api'
import { formatDateTime, formatDuration, formatMegabytes } from '../../lib/format'
import { useCreateShort, useMeta, useShort } from '../../lib/queries'

const STEPS: { stage: VideoStage; name: string; doing: string }[] = [
  { stage: 'script', name: 'Сценарий', doing: 'Пишем сценарий' },
  { stage: 'voice', name: 'Озвучка', doing: 'Озвучиваем' },
  { stage: 'render', name: 'Монтаж', doing: 'Монтируем кадры' },
]

/** What the screen reader announces: one line per state change. */
function announcement(video: Video | null): string {
  if (!video) return ''
  if (video.status === 'queued') return 'Видео в очереди'
  if (video.status === 'running') {
    return STEPS.find((step) => step.stage === video.stage)?.doing ?? 'Видео собирается'
  }
  return video.status === 'done' ? 'Видео готово' : 'Видео собрать не удалось'
}

function Progress({ video }: { video: Video }) {
  const current = STEPS.findIndex((step) => step.stage === video.stage)
  const isQueued = video.status === 'queued'
  const percent = Math.round(video.progress * 100)
  return (
    <div>
      <p className="text-sm font-semibold">{announcement(video)}</p>
      {/* While queued there is no progress to report: the bar is indeterminate. */}
      <div
        role="progressbar"
        aria-label="Готовность видео"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={isQueued ? undefined : percent}
        aria-valuetext={isQueued ? 'В очереди' : `${percent}%`}
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-sunken"
      >
        <motion.div
          className="h-full origin-left rounded-full bg-spark"
          initial={false}
          animate={{ scaleX: Math.max(percent, 3) / 100 }}
          transition={{ type: 'spring', stiffness: 70, damping: 20 }}
        />
      </div>
      <ol className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {STEPS.map((step, index) => {
          const isDone = !isQueued && index < current
          const isActive = !isQueued && index === current
          return (
            <li
              key={step.stage}
              aria-current={isActive ? 'step' : undefined}
              className={clsx(
                'flex items-center gap-2 text-xs',
                isDone || isActive ? 'text-text' : 'text-faint',
              )}
            >
              <span
                className={clsx(
                  'grid size-5 place-items-center rounded-full text-[10px] font-semibold',
                  isDone && 'bg-spark text-[#0b0f17]',
                  isActive && 'bg-spark-soft text-spark',
                  !isDone && !isActive && 'bg-sunken',
                )}
              >
                {isDone ? <Check size={11} strokeWidth={3} aria-hidden /> : index + 1}
              </span>
              {step.name}
              {isDone && <span className="sr-only"> (готово)</span>}
            </li>
          )
        })}
      </ol>
      <p className="mt-4 text-xs text-muted">
        Обычно это занимает одну-три минуты. Можно читать выпуск: видео появится здесь.
      </p>
    </div>
  )
}

function Player({ video }: { video: Video }) {
  const details = [
    video.duration_ms ? formatDuration(video.duration_ms) : null,
    video.voice ? `голос ${video.voice.replace(/^qwen3-tts:/, 'Qwen3-TTS ')}` : 'без озвучки',
    video.by_model ? 'сценарий модели' : 'сценарий из выжимок',
    video.size_bytes ? formatMegabytes(video.size_bytes) : null,
  ].filter(Boolean)
  // The address carries the version of the cut, so a new cut is never
  // served from the browser cache, in the player or as a download.
  const url = video.url ?? ''
  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-end">
      {/* 9:16, as it will be watched on a phone. */}
      <video
        key={url}
        src={url}
        controls
        playsInline
        preload="metadata"
        aria-label="Короткое видео по выпуску, субтитры встроены в кадр"
        className="aspect-[9/16] w-full max-w-[17rem] rounded-xl bg-[#070a12] shadow-card"
      />
      <div className="min-w-0 space-y-3">
        <p className="text-sm text-muted">{details.join(' · ')}</p>
        {video.finished_at && (
          <p className="text-xs text-faint">Готово {formatDateTime(video.finished_at)}</p>
        )}
        <a href={`${url}&download=1`} download className={buttonClass('primary', 'sm')}>
          <Download size={15} />
          Скачать MP4
        </a>
      </div>
    </div>
  )
}

/**
 * The short video of a digest: order it, watch it being made, play and
 * download it. Shown only when the server can render videos.
 */
export function ShortPanel({ digestId }: { digestId: string }) {
  const meta = useMeta()
  const isAvailable = meta.data?.shorts === true
  const short = useShort(digestId, isAvailable)
  const create = useCreateShort(digestId)
  if (!isAvailable) return null

  const video = short.data ?? null
  const isBusy = video?.status === 'queued' || video?.status === 'running'
  const hasVoice = meta.data?.shorts_voice === true
  const state = video?.status ?? 'none'

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-semibold">
            <Clapperboard size={17} className="text-spark" aria-hidden />
            Короткое видео
          </h3>
          <p className="mt-1 max-w-prose text-sm text-muted">
            Вертикальный ролик на полминуты-минуту: главные новости выпуска, крупные цифры и
            субтитры по словам.
          </p>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-faint">
            {hasVoice ? <Mic size={13} aria-hidden /> : <Captions size={13} aria-hidden />}
            {hasVoice
              ? 'Озвучка Qwen3-TTS'
              : 'Озвучка на этом сервере не подключена: историю рассказывают субтитры'}
          </p>
        </div>
        {!isBusy && (
          <Button
            variant={state === 'none' ? 'primary' : 'ghost'}
            size="sm"
            icon={state === 'none' ? <Clapperboard size={15} /> : <RotateCcw size={15} />}
            isBusy={create.isPending}
            onClick={() => create.mutate()}
          >
            {state === 'none' ? 'Сделать видео' : 'Переснять'}
          </Button>
        )}
      </div>

      <ErrorNote error={create.error ?? short.error} />
      {/* Lives outside the animated block: a live region is announced only
          when it changes, not when it appears together with its text. */}
      <p className="sr-only" aria-live="polite">
        {announcement(video)}
      </p>

      <AnimatePresence mode="wait" initial={false}>
        {video && (
          <motion.div
            key={isBusy ? 'progress' : video.status}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: EASE }}
            className="mt-5"
          >
            {isBusy && <Progress video={video} />}
            {video.status === 'done' && <Player video={video} />}
            {video.status === 'failed' && (
              <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                {video.error ?? 'Видео собрать не удалось.'}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}
