import { useEffect, useRef, useState } from 'react'
import { Play, Square } from '../../components/icons'
import { SelectField } from '../../components/SelectField'
import { Button } from '../../components/ui'
import type { VoiceOption } from '../../lib/api'
import { toast } from '../../lib/toast'
import { voiceSampleUrl } from '../../lib/voices'

type Props = {
  voices: VoiceOption[]
  value: string | null
  onChange: (id: string) => void
}

/**
 * The voice of a narration: a drop-down list and, beside it, a few seconds of
 * the chosen voice. While a sample plays, picking another voice plays that one.
 */
export function VoiceSelect({ voices, value, onChange }: Props) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState<string | null>(null)
  const current = voices.find((voice) => voice.id === value)

  // Leaving the page stops the sound.
  useEffect(() => () => audio.current?.pause(), [])

  const stop = () => {
    audio.current?.pause()
    audio.current = null
    setPlaying(null)
  }
  const listen = (id: string) => {
    audio.current?.pause()
    const sample = new Audio(voiceSampleUrl(id))
    sample.onended = () => setPlaying(null)
    const failed = () => {
      setPlaying(null)
      toast.error('Пример голоса не загрузился')
    }
    sample.onerror = failed
    audio.current = sample
    setPlaying(id)
    sample.play()?.catch(failed)
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="min-w-48 flex-1 space-y-1.5">
        {/* The select names itself for assistive tech; this is the visible label. */}
        <p aria-hidden className="text-xs text-muted">
          Голос
        </p>
        <SelectField
          label="Голос"
          value={value ?? ''}
          onChange={(id) => {
            onChange(id)
            if (playing !== null && voices.some((voice) => voice.id === id && voice.sample)) {
              listen(id)
            } else if (playing !== null) {
              stop()
            }
          }}
          options={voices.map((voice) => ({ value: voice.id, label: voice.title }))}
        />
      </div>
      {current?.sample && (
        <Button
          variant="ghost"
          size="sm"
          icon={playing ? <Square size={14} /> : <Play size={14} />}
          aria-label={playing ? 'Остановить пример' : `Послушать голос «${current.title}»`}
          onClick={() => (playing ? stop() : listen(current.id))}
        >
          {playing ? 'Стоп' : 'Послушать'}
        </Button>
      )}
    </div>
  )
}
