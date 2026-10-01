import type { VoiceOption } from './api'

/**
 * The voice to show as chosen and to send: the reader's pick, else the voice
 * of the last video, else the service's default. A voice the service no
 * longer offers is skipped, so the pill that looks selected is always the
 * one that is sent.
 */
export function chosenVoice(
  voices: VoiceOption[],
  picked: string | null,
  previous: string | null | undefined,
): string | null {
  const offered = (id: string | null | undefined) =>
    id != null && voices.some((voice) => voice.id === id) ? id : null
  return (
    offered(picked) ??
    offered(previous) ??
    voices.find((voice) => voice.default)?.id ??
    voices[0]?.id ??
    null
  )
}
