import type { VoiceEngine, VoiceOption } from './api'

/** The engines' names as the reader sees them. */
export const ENGINE_NAMES: Record<VoiceEngine, string> = {
  'qwen3-tts': 'Qwen3-TTS',
  yandex: 'Yandex SpeechKit',
}

/**
 * A stored voice, "qwen3-tts:anchor" or "yandex:zahar", as its engine and
 * speaker. A voice without a known engine is the voice service's.
 */
export function parseVoice(stored: string): { engine: VoiceEngine; id: string } {
  const match = /^(qwen3-tts|yandex):(.+)$/.exec(stored)
  if (!match) return { engine: 'qwen3-tts', id: stored }
  return { engine: match[1] as VoiceEngine, id: match[2] }
}

/**
 * The voice by the name the list of voices gives it, "Захар"; one the list
 * no longer has by its engine and id, "Yandex SpeechKit zahar".
 */
export function voiceTitle(
  stored: string,
  voices: VoiceOption[],
): { title: string; known: boolean } {
  const { engine, id } = parseVoice(stored)
  const title = voices.find((voice) => voice.id === id)?.title
  return title ? { title, known: true } : { title: `${ENGINE_NAMES[engine]} ${id}`, known: false }
}

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
