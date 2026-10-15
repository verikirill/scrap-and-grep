// An answer about a digest as the reader sees it come in: word by word, with
// its "[2]" standing for the entries the model drew on.

/** A citation of an entry, a gap kept as written, or a word with its turn to show. */
export type AnswerPiece =
  | { kind: 'cite'; number: number }
  | { kind: 'gap'; text: string }
  | { kind: 'word'; text: string; turn: number }

const CITATION = /(\[\d{1,3}\])/
const CITED = /^\[(\d{1,3})\]$/

/** The answer in pieces, its words numbered from 1 through the citations between them. */
export function answerPieces(text: string): AnswerPiece[] {
  const pieces: AnswerPiece[] = []
  let turn = 0
  for (const part of text.split(CITATION)) {
    const cite = CITED.exec(part)
    if (cite) {
      pieces.push({ kind: 'cite', number: Number(cite[1]) })
      continue
    }
    for (const piece of part.split(/(\s+)/)) {
      if (piece === '') continue
      if (/^\s+$/.test(piece)) {
        pieces.push({ kind: 'gap', text: piece })
      } else {
        turn += 1
        pieces.push({ kind: 'word', text: piece, turn })
      }
    }
  }
  return pieces
}
