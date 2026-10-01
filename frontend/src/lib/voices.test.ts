import { describe, expect, it } from 'vitest'
import type { VoiceOption } from './api'
import { chosenVoice } from './voices'

const VOICES: VoiceOption[] = [
  { id: 'anchor', title: 'Ведущий', default: true },
  { id: 'blogger-2', title: 'Энергично', default: false },
]

describe('chosenVoice', () => {
  it('prefers the pick, then the last video, then the default', () => {
    expect(chosenVoice(VOICES, 'blogger-2', 'anchor')).toBe('blogger-2')
    expect(chosenVoice(VOICES, null, 'blogger-2')).toBe('blogger-2')
    expect(chosenVoice(VOICES, null, null)).toBe('anchor')
  })

  it('skips a voice the service no longer offers', () => {
    expect(chosenVoice(VOICES, 'removed', 'gone')).toBe('anchor')
  })

  it('has nothing to choose without voices', () => {
    expect(chosenVoice([], 'anchor', 'anchor')).toBeNull()
  })
})
