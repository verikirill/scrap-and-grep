import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, SAFE, TEXT_FONT, alpha } from '../theme'
import { Words } from './Words'

type Props = {
  brand: string
  outro: string
}

/** Closing card: the brand mark and where to read the full digest. */
export function OutroScene({ brand, outro }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const mark = spring({ frame, fps, config: { damping: 10, stiffness: 120 } })

  return (
    <AbsoluteFill style={{ alignItems: 'center' }}>
      <div
        style={{
          marginTop: SAFE.top + 230,
          width: 220,
          height: 220,
          borderRadius: 60,
          background: COLORS.accent,
          display: 'grid',
          placeItems: 'center',
          transform: `scale(${mark}) rotate(${(1 - mark) * 25}deg)`,
          boxShadow: `0 30px 120px ${alpha(COLORS.accent, 0.45)}`,
        }}
      >
        <div
          style={{
            width: 120,
            height: 120,
            borderRadius: '50%',
            border: `12px solid ${COLORS.ink}`,
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 30,
              borderRadius: '50%',
              background: COLORS.ink,
            }}
          />
        </div>
      </div>
      <div
        style={{
          marginTop: 60,
          fontFamily: DISPLAY_FONT,
          fontWeight: 800,
          fontSize: 72,
          color: COLORS.text,
          letterSpacing: 2,
          textTransform: 'uppercase',
        }}
      >
        {brand}
      </div>
      <Words
        text={outro}
        delay={8}
        stagger={3}
        style={{
          marginTop: 36,
          maxWidth: 860,
          justifyContent: 'center',
          textAlign: 'center',
          fontFamily: TEXT_FONT,
          fontWeight: 700,
          fontSize: 50,
          lineHeight: 1.25,
          color: COLORS.muted,
        }}
      />
    </AbsoluteFill>
  )
}
