import { describe, expect, it } from 'vitest'
import { applyReaction } from './queries'

describe('applyReaction', () => {
  it('replaces a dislike with a like, as the server does', () => {
    expect(applyReaction(['dislike', 'save'], 'like', true)).toEqual(['save', 'like'])
  })

  it('takes a signal back without touching the others', () => {
    expect(applyReaction(['like', 'save', 'open'], 'like', false)).toEqual(['save', 'open'])
  })

  it('keeps a save and a hide independent of each other', () => {
    expect(applyReaction(['save'], 'hide', true)).toEqual(['save', 'hide'])
  })
})
