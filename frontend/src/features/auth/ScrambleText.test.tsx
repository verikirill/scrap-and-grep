import { act, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ScrambleText } from './ScrambleText'

const motion = vi.hoisted(() => ({ reduced: false }))
vi.mock('motion/react', async (importOriginal) => ({
  ...(await importOriginal<typeof import('motion/react')>()),
  useReducedMotion: () => motion.reduced,
}))

describe('ScrambleText', () => {
  afterEach(() => {
    vi.useRealTimers()
    motion.reduced = false
  })

  it('decodes each word in turn and comes back to the first', () => {
    vi.useFakeTimers()
    const { container } = render(<ScrambleText words={['инженера АСУ ТП', 'аналитика ИБ']} />)

    // Settled after its letters run out of glyphs, then held, then the next.
    act(() => vi.advanceTimersByTime(40 * 25))
    expect(container.textContent).toBe('инженера АСУ ТП')
    act(() => vi.advanceTimersByTime(2800))
    act(() => vi.advanceTimersByTime(40 * 25))
    expect(container.textContent).toBe('аналитика ИБ')
    act(() => vi.advanceTimersByTime(2800))
    act(() => vi.advanceTimersByTime(40 * 25))
    expect(container.textContent).toBe('инженера АСУ ТП')
  })

  it('keeps the first word still under reduce motion', () => {
    motion.reduced = true
    vi.useFakeTimers()
    const { container } = render(<ScrambleText words={['инженера АСУ ТП', 'аналитика ИБ']} />)

    act(() => vi.advanceTimersByTime(10_000))

    expect(container.textContent).toBe('инженера АСУ ТП')
  })
})
