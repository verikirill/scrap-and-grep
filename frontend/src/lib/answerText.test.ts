import { describe, expect, it } from 'vitest'
import { answerPieces } from './answerText'

describe('answerPieces', () => {
  it('cuts an answer into words, gaps and citations, the words counted through the citations', () => {
    expect(answerPieces('Обновите S7-1500 [1], затем VPN [2].')).toEqual([
      { kind: 'word', text: 'Обновите', turn: 1 },
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: 'S7-1500', turn: 2 },
      { kind: 'gap', text: ' ' },
      { kind: 'cite', number: 1 },
      { kind: 'word', text: ',', turn: 3 },
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: 'затем', turn: 4 },
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: 'VPN', turn: 5 },
      { kind: 'gap', text: ' ' },
      { kind: 'cite', number: 2 },
      { kind: 'word', text: '.', turn: 6 },
    ])
  })

  it('keeps the gaps as the model wrote them, a leading one and line breaks included', () => {
    expect(answerPieces(' Да.\n\nНет')).toEqual([
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: 'Да.', turn: 1 },
      { kind: 'gap', text: '\n\n' },
      { kind: 'word', text: 'Нет', turn: 2 },
    ])
  })

  it('takes one to three digits in brackets for a citation and leaves longer numbers as text', () => {
    expect(answerPieces('См. [1234] и [12]')).toEqual([
      { kind: 'word', text: 'См.', turn: 1 },
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: '[1234]', turn: 2 },
      { kind: 'gap', text: ' ' },
      { kind: 'word', text: 'и', turn: 3 },
      { kind: 'gap', text: ' ' },
      { kind: 'cite', number: 12 },
    ])
  })
})
