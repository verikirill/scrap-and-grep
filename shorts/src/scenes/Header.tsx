import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, SAFE, TEXT_FONT } from '../theme'
import type { Beat } from '../types'

type Props = {
  brand: string
  period: string
  beats: Beat[]
}

/** Story-style progress segments, one per news item, and the brand line. */
export function Header({ brand, period, beats }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const nowMs = (frame / fps) * 1000

  return (
    <div
      style={{
        position: 'absolute',
        top: SAFE.top - 90,
        left: SAFE.side,
        right: SAFE.side,
        fontFamily: TEXT_FONT,
      }}
    >
      <div style={{ display: 'flex', gap: 10 }}>
        {beats.map((beat, index) => {
          const share = interpolate(nowMs, [beat.startMs, beat.endMs], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
          return (
            <div
              key={index}
              style={{
                flex: 1,
                height: 8,
                borderRadius: 8,
                background: 'rgba(255, 255, 255, 0.16)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  background: COLORS.text,
                  transform: `scaleX(${share})`,
                  transformOrigin: 'left',
                }}
              />
            </div>
          )
        })}
      </div>
      <div
        style={{
          marginTop: 26,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          color: COLORS.muted,
          fontSize: 30,
          fontWeight: 600,
          letterSpacing: 2,
          textTransform: 'uppercase',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 14, color: COLORS.text }}>
          <span
            style={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              background: COLORS.accent,
              boxShadow: `0 0 0 8px rgba(125, 155, 255, 0.22)`,
            }}
          />
          {brand}
        </span>
        <span>{period}</span>
      </div>
    </div>
  )
}
