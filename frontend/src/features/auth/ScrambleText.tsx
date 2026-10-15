import { useEffect, useState } from 'react'
import { useReducedMotion } from 'motion/react'

// Glyphs a word runs through on its way in: letters, digits and the marks of
// the terminal on the left.
const GLYPHS = 'АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ0123456789#$%&*<>/'
const FRAME_MS = 40
// Frames a letter keeps changing before it settles, one more for each next letter.
const SETTLE_FRAMES = 6
const HOLD_MS = 2800
const SEPARATOR = '|'

function scrambled(target: string, frame: number): string {
  return Array.from(target, (char, index) => {
    if (char === ' ' || frame >= SETTLE_FRAMES + index) return char
    return GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
  }).join('')
}

/**
 * The words in turn, each decoded letter by letter from random glyphs, as a
 * terminal prints a match. Still under "reduce motion": the first word stays.
 */
export function ScrambleText({ words, className }: { words: string[]; className?: string }) {
  const isStill = useReducedMotion() ?? false
  const [index, setIndex] = useState(0)
  const [text, setText] = useState(words[0] ?? '')
  // The words by value: a list written inline is a new array on every render,
  // and the decoding must not start over each time.
  const key = words.join(SEPARATOR)

  useEffect(() => {
    const list = key.split(SEPARATOR)
    if (isStill || list.length < 2) return
    const target = list[index % list.length]
    const frames = SETTLE_FRAMES + target.length
    let frame = 0
    let hold = 0
    const timer = window.setInterval(() => {
      frame += 1
      setText(scrambled(target, frame))
      if (frame >= frames) {
        window.clearInterval(timer)
        hold = window.setTimeout(() => setIndex((value) => (value + 1) % list.length), HOLD_MS)
      }
    }, FRAME_MS)
    return () => {
      window.clearInterval(timer)
      window.clearTimeout(hold)
    }
  }, [index, isStill, key])

  return (
    <span aria-hidden className={className}>
      {isStill ? words[0] : text}
    </span>
  )
}
