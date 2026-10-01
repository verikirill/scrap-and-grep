import { Check } from 'lucide-react'
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, TEXT_FONT } from '../theme'

type Props = {
  points: string[]
  color: string
  durationInFrames: number
}

/** Frames at which the points appear: spread over the middle of the narration. */
export function pointTimes(count: number, durationInFrames: number): number[] {
  const first = 0.22
  const last = count > 1 ? 0.64 : first
  return Array.from({ length: count }, (_, index) =>
    Math.round(durationInFrames * (first + ((last - first) * index) / Math.max(1, count - 1))),
  )
}

/** Short facts of the news, ticked off one by one while it is told. */
export function Points({ points, color, durationInFrames }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const times = pointTimes(points.length, durationInFrames)

  return (
    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 18 }}>
      {points.map((point, index) => {
        const shown = spring({ frame: frame - times[index], fps, config: { damping: 14, stiffness: 160 } })
        return (
          <li
            key={index}
            style={{
              display: 'flex',
              gap: 14,
              alignItems: 'flex-start',
              opacity: Math.min(1, shown * 1.5),
              transform: `translateX(${(1 - shown) * 60}px)`,
              fontFamily: TEXT_FONT,
              fontWeight: 700,
              fontSize: 32,
              lineHeight: 1.2,
              color: COLORS.text,
            }}
          >
            <span
              style={{
                flex: 'none',
                marginTop: 2,
                width: 36,
                height: 36,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                background: color,
                transform: `scale(${shown})`,
              }}
            >
              <Check size={24} color={COLORS.ink} strokeWidth={3.5} />
            </span>
            {point}
          </li>
        )
      })}
    </ul>
  )
}
