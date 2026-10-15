import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { REVEAL_EVENT, showEntry } from './entryNav'

/** An entry of the issue as DigestView draws it, with its jump observed. */
function addEntry(number: number) {
  const entry = document.createElement('article')
  entry.id = `entry-${number}`
  // jsdom has no scrolling or Web Animations.
  const scrollIntoView = vi.fn()
  const animate = vi.fn()
  Object.assign(entry, { scrollIntoView, animate })
  document.body.append(entry)
  return { entry, scrollIntoView, animate }
}

describe('showEntry', () => {
  const asked: number[] = []
  const onReveal = (event: Event) => asked.push((event as CustomEvent<number>).detail)
  beforeEach(() => {
    vi.useFakeTimers()
    asked.length = 0
    window.addEventListener(REVEAL_EVENT, onReveal)
  })
  afterEach(() => {
    window.removeEventListener(REVEAL_EVENT, onReveal)
    document.body.replaceChildren()
  })

  it('scrolls to an entry on the page and makes it blink, without asking sections', () => {
    const { scrollIntoView, animate } = addEntry(4)

    showEntry(4)

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(animate).toHaveBeenCalledOnce()
    expect(asked).toEqual([])
  })

  it('asks the sections to open a hidden entry and scrolls once it has unfolded', () => {
    showEntry(7)
    expect(asked).toEqual([7])

    vi.advanceTimersByTime(100)
    const { scrollIntoView } = addEntry(7)
    vi.advanceTimersByTime(50)
    // The section unfolds over 0,28 s: a scroll before that would land short.
    expect(scrollIntoView).not.toHaveBeenCalled()

    vi.advanceTimersByTime(340)
    expect(scrollIntoView).toHaveBeenCalledOnce()
  })

  it('gives up after a second when no section holds the entry', () => {
    showEntry(9)
    vi.advanceTimersByTime(1000)
    const { scrollIntoView } = addEntry(9)

    vi.runAllTimers()

    expect(scrollIntoView).not.toHaveBeenCalled()
  })
})
