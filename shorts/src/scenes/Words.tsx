import type { CSSProperties } from 'react'
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'

type Props = {
  text: string
  /** Frames between two words appearing. */
  stagger?: number
  /** Frame (within the sequence) the first word starts at. */
  delay?: number
  style?: CSSProperties
  /** Words to paint in the accent colour, by index. */
  accent?: { indexes: number[]; color: string }
  /** Shown from the first frame and settling from a larger size, instead of
   * rising out of nothing: the first frame is the video's thumbnail. */
  isVisibleAtStart?: boolean
}

/**
 * Text that arrives word by word: each word rises, grows to size and fades
 * in on a spring. Short-video audiences read one word at a time anyway.
 */
export function Words({ text, stagger = 3, delay = 0, style, accent, isVisibleAtStart = false }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const words = text.split(/\s+/).filter(Boolean)
  // The settle is a scale of the whole block: scaling words one by one would
  // eat the gaps between them.
  const settle = isVisibleAtStart
    ? spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 140 } })
    : 1

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        columnGap: '0.28em',
        rowGap: '0.08em',
        transform: `scale(${1.06 - settle * 0.06})`,
        transformOrigin: 'left top',
        ...style,
      }}
    >
      {words.map((word, index) => {
        const progress = spring({
          frame: frame - delay - index * stagger,
          fps,
          config: { damping: 14, stiffness: 170, mass: 0.7 },
        })
        const isAccent = accent?.indexes.includes(index)
        const motion = isVisibleAtStart
          ? { opacity: 1, transform: `translateY(${(1 - progress) * 14}px)` }
          : {
              opacity: Math.min(1, progress * 1.6),
              transform: `translateY(${(1 - progress) * 46}px) scale(${0.86 + progress * 0.14})`,
            }
        return (
          <span
            key={`${index}-${word}`}
            style={{
              display: 'inline-block',
              ...motion,
              color: isAccent ? accent?.color : undefined,
            }}
          >
            {word}
          </span>
        )
      })}
    </div>
  )
}
