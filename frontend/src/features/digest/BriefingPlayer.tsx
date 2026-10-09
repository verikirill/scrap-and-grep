import { useId, useState } from 'react'
import { Download, Loader2, Mic, RotateCcw } from '../../components/icons'
import { SelectField } from '../../components/SelectField'
import { buttonClass } from '../../components/tokens'
import { Button, ErrorNote } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { Briefing, Digest, VoiceOption } from '../../lib/api'
import { formatDateTime, formatMegabytes } from '../../lib/format'
import { useBriefing, useCreateBriefing } from '../../lib/queries'
import { chosenVoice } from '../../lib/voices'

const isBusy = (briefing: Briefing | null) =>
  briefing?.status === 'queued' || briefing?.status === 'running'

/** What the screen reader announces: one line per state change. */
function announcement(briefing: Briefing | null): string {
  if (!briefing) return ''
  if (briefing.status === 'queued') return 'Брифинг в очереди'
  if (briefing.status === 'running') return 'Брифинг озвучивается'
  return briefing.status === 'done' ? 'Брифинг готов' : 'Не удалось озвучить брифинг'
}

function voiceName(briefing: Briefing, voices: VoiceOption[]): string | null {
  const id = briefing.voice?.replace(/^qwen3-tts:/, '')
  if (!id) return null
  return `голос: ${voices.find((voice) => voice.id === id)?.title ?? id}`
}

function Progress({ briefing }: { briefing: Briefing }) {
  const isQueued = briefing.status === 'queued'
  const percent = Math.round(briefing.progress * 100)
  return (
    <div>
      <p className="text-sm font-semibold">{announcement(briefing)}</p>
      <div
        role="progressbar"
        aria-label="Готовность брифинга"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={isQueued ? undefined : percent}
        aria-valuetext={isQueued ? 'В очереди' : `${percent}%`}
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-secondary"
      >
        <div
          className="h-full origin-left rounded-full bg-warning transition-transform duration-500"
          style={{ transform: `scaleX(${Math.max(percent, 3) / 100})` }}
        />
      </div>
      <p className="mt-2 text-xs text-muted">
        Озвучиваем выпуск по частям. Окно можно закрыть, брифинг соберётся в фоне.
      </p>
    </div>
  )
}

function Player({ briefing, voices }: { briefing: Briefing; voices: VoiceOption[] }) {
  // The address carries the version of the recording, so a new one is never
  // served from the browser cache, in the player or as a download.
  const url = briefing.url ?? ''
  const transcriptId = useId()
  // The player shows the length itself, to the second of the file.
  const details = [
    voiceName(briefing, voices),
    briefing.size_bytes ? formatMegabytes(briefing.size_bytes) : null,
  ].filter(Boolean)
  return (
    <div className="space-y-3">
      <audio
        key={url}
        src={url}
        controls
        preload="metadata"
        aria-label="Голосовой брифинг по выпуску"
        // The transcript below is the text alternative of the recording.
        aria-describedby={transcriptId}
        className="w-full"
      />
      <p className="text-xs text-muted">
        {details.join(' · ')}
        {briefing.finished_at && ` · готово ${formatDateTime(briefing.finished_at)}`}
      </p>
      <details className="rounded-lg bg-surface-secondary px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium">Текст брифинга</summary>
        <div
          id={transcriptId}
          className="mt-2 max-h-64 space-y-2 overflow-y-auto text-sm leading-relaxed"
        >
          {briefing.lines.map((line, index) => (
            <p key={index}>{line}</p>
          ))}
        </div>
      </details>
      <a href={`${url}&download=1`} download className={buttonClass('ghost', 'sm')}>
        <Download size={15} />
        Скачать WAV
      </a>
    </div>
  )
}

/**
 * The spoken brief of a management digest: a button in the digest's header
 * that orders it, and a window to follow it, listen to it and read it.
 * Shown only for a finished management digest on a server with a voice.
 */
export function BriefingPlayer({ digest }: { digest: Digest }) {
  const isWanted = digest.audience === 'management' && digest.status === 'done'
  const state = useBriefing(digest.id, isWanted)
  const create = useCreateBriefing(digest.id)
  const [isOpen, setOpen] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  if (!isWanted || state.data?.available !== true) return null

  const briefing = state.data.briefing
  const voices = state.data.voices
  const voice = chosenVoice(voices, picked, briefing?.requested_voice)
  const order = () => create.mutate(voices.length > 0 ? voice : null)
  const busy = isBusy(briefing)

  const open = () => {
    setOpen(true)
    // The first press orders the brief: there is nothing to listen to yet.
    if (!briefing && !create.isPending) order()
  }

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        icon={busy ? <Loader2 size={15} className="animate-spin" /> : <Mic size={15} />}
        onClick={open}
      >
        {busy ? 'Озвучиваем брифинг' : 'Слушать брифинг'}
      </Button>
      <Dialog open={isOpen} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Mic size={18} className="text-warning" aria-hidden />
              Голосовой брифинг
            </DialogTitle>
            <DialogDescription>
              Полторы-две минуты для руководства: главное за период простыми словами, без номеров
              уязвимостей и технических деталей.
            </DialogDescription>
          </DialogHeader>

          {/* Outside the changing block: a live region is announced when it
              changes, not when it appears together with its text. */}
          <p className="sr-only" aria-live="polite">
            {announcement(briefing)}
          </p>
          <ErrorNote error={create.error ?? state.error} />

          {!briefing && create.isPending && (
            <p className="text-sm text-muted">Заказываем брифинг…</p>
          )}
          {briefing && busy && <Progress briefing={briefing} />}
          {briefing?.status === 'done' && <Player briefing={briefing} voices={voices} />}
          {briefing?.status === 'failed' && (
            <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {briefing.error ?? 'Не удалось озвучить брифинг.'}
            </p>
          )}

          {briefing && !busy && (
            <div className="flex flex-wrap items-end gap-3 border-t border-separator pt-4">
              {voices.length > 0 && (
                <div className="min-w-48 flex-1 space-y-1.5">
                  {/* The select names itself for assistive tech; this is the visible label. */}
                  <p aria-hidden className="text-xs text-muted">
                    Голос
                  </p>
                  <SelectField
                    label="Голос"
                    value={voice ?? ''}
                    onChange={setPicked}
                    options={voices.map((option) => ({ value: option.id, label: option.title }))}
                  />
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                icon={<RotateCcw size={15} />}
                isBusy={create.isPending}
                onClick={order}
              >
                {briefing.status === 'failed' ? 'Попробовать снова' : 'Озвучить заново'}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
