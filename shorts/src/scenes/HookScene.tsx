import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, SAFE, TEXT_FONT } from '../theme'
import { Words } from './Words'

type Props = {
  hook: string
  audience: string
  durationInFrames: number
}

/** The first seconds: a loud promise of what is coming, over a pulsing ring. */
export function HookScene({ hook, audience, durationInFrames }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const pulse = (frame % (fps * 1.2)) / (fps * 1.2)
  const exit = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  // Everything is on screen from the first frame, which is the thumbnail;
  // the springs only settle it into place.
  const badge = spring({ frame, fps, config: { damping: 12 } })
  // The full stop helps the voice end the sentence; on screen it is noise.
  const shown = hook.replace(/[.!…]+$/, '')
  const words = shown.split(/\s+/).filter(Boolean)
  // Uppercase Unbounded is wide: about twelve letters a line at full size.
  const fontSize = shown.length > 44 ? 72 : shown.length > 28 ? 84 : 96
  // The number or the first word carries the promise; it gets the colour.
  const accentIndex = Math.max(
    0,
    words.findIndex((word) => /\d/.test(word)),
  )

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: 760,
          width: 900,
          height: 900,
          marginLeft: -450,
          marginTop: -450,
          borderRadius: '50%',
          border: `4px solid ${COLORS.accent}`,
          opacity: 0.5 * (1 - pulse),
          transform: `scale(${0.4 + pulse * 0.8})`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: SAFE.top + 250,
          left: SAFE.side,
          right: SAFE.side,
        }}
      >
        <div
          style={{
            display: 'inline-block',
            padding: '14px 28px',
            borderRadius: 999,
            background: COLORS.spark,
            color: COLORS.ink,
            fontFamily: TEXT_FONT,
            fontWeight: 800,
            fontSize: 34,
            letterSpacing: 2,
            textTransform: 'uppercase',
            transform: `scale(${0.88 + badge * 0.12})`,
            transformOrigin: 'left center',
          }}
        >
          {audience}
        </div>
        <Words
          text={shown}
          delay={2}
          stagger={3}
          isVisibleAtStart
          accent={{ indexes: [accentIndex], color: COLORS.caption }}
          style={{
            marginTop: 48,
            fontFamily: DISPLAY_FONT,
            fontWeight: 800,
            fontSize,
            lineHeight: 1.08,
            color: COLORS.text,
            textTransform: 'uppercase',
          }}
        />
      </div>
    </AbsoluteFill>
  )
}
