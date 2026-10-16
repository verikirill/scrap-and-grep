import { screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { VoiceOption } from '../../lib/api'
import { renderWithProviders } from '../../test/render'
import { VoiceSelect } from './VoiceSelect'

const VOICES: VoiceOption[] = [
  { id: 'zahar', title: 'Захар', default: true, sample: true },
  { id: 'alena', title: 'Алёна', default: false, sample: true },
  { id: 'new', title: 'Новый', default: false, sample: false },
]

/** A stand-in for the browser's audio: what was played, and stopped. */
function fakeAudio() {
  const played: string[] = []
  const paused: string[] = []
  class FakeAudio {
    onended: (() => void) | null = null
    onerror: (() => void) | null = null
    readonly src: string
    constructor(src: string) {
      this.src = src
    }
    play() {
      played.push(this.src)
      return Promise.resolve()
    }
    pause() {
      paused.push(this.src)
    }
  }
  vi.stubGlobal('Audio', FakeAudio)
  return { played, paused }
}

function Picker() {
  const [value, setValue] = useState<string | null>('zahar')
  return <VoiceSelect voices={VOICES} value={value} onChange={setValue} />
}

afterEach(() => vi.unstubAllGlobals())

describe('VoiceSelect', () => {
  it('plays the chosen voice, follows a new pick while playing and stops', async () => {
    const { played, paused } = fakeAudio()
    const { user } = renderWithProviders(<Picker />)

    await user.click(screen.getByRole('button', { name: 'Послушать голос «Захар»' }))
    expect(played).toEqual(['/api/v1/voices/zahar/sample.wav'])

    await user.click(screen.getByRole('button', { name: /Голос: Захар$/ }))
    await user.click(await screen.findByRole('option', { name: 'Алёна' }))
    expect(played.at(-1)).toBe('/api/v1/voices/alena/sample.wav')

    await user.click(screen.getByRole('button', { name: 'Остановить пример' }))
    expect(paused.at(-1)).toBe('/api/v1/voices/alena/sample.wav')
    expect(screen.getByRole('button', { name: 'Послушать голос «Алёна»' })).toBeInTheDocument()
  })

  it('offers nothing to hear for a voice without a sample yet', async () => {
    fakeAudio()
    const { user } = renderWithProviders(<Picker />)

    await user.click(screen.getByRole('button', { name: /Голос: Захар$/ }))
    await user.click(await screen.findByRole('option', { name: 'Новый' }))

    expect(screen.queryByRole('button', { name: /Послушать/ })).toBeNull()
  })
})
