import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, SAFE, TEXT_FONT } from '../theme'
import type { Beat } from '../types'
import { Words } from './Words'

type Props = {
  beat: Beat
  number: number
  durationInFrames: number
}

/**
 * One news item: kicker, headline, a big fact card and the source. It slides
 * in from the right and hands over to the next one with a quick fade.
 */
export function BeatScene({ beat, number, durationInFrames }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 120 } })
  const exit = interpolate(frame, [durationInFrames - 7, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  // The fact lands when the narration is about a third of the way in.
  const factAt = Math.round(durationInFrames * 0.32)
  const fact = spring({ frame: frame - factAt, fps, config: { damping: 11, stiffness: 150 } })
  const titleWords = beat.title.split(/\s+/).filter(Boolean)
  // Titles run up to about 90 characters; long ones step down so the fact
  // card and the source still fit above the captions.
  const titleSize = beat.title.length > 70 ? 58 : beat.title.length > 48 ? 66 : 78

  return (
    <AbsoluteFill
      style={{
        opacity: exit,
        transform: `translateX(${(1 - enter) * 140}px)`,
      }}
    >
      <div style={{ position: 'absolute', top: SAFE.top + 170, left: SAFE.side, right: SAFE.side }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 18,
            fontFamily: TEXT_FONT,
            fontWeight: 800,
            fontSize: 36,
            letterSpacing: 3,
            textTransform: 'uppercase',
            color: COLORS.accent,
          }}
        >
          <span
            style={{
              padding: '8px 18px',
              borderRadius: 14,
              background: COLORS.accent,
              color: COLORS.ink,
            }}
          >
            {String(number).padStart(2, '0')}
          </span>
          {beat.kicker}
        </div>
        <Words
          text={beat.title}
          delay={5}
          stagger={3}
          accent={{ indexes: [titleWords.length - 1], color: COLORS.spark }}
          style={{
            marginTop: 40,
            fontFamily: DISPLAY_FONT,
            fontWeight: 700,
            fontSize: titleSize,
            lineHeight: 1.12,
            color: COLORS.text,
          }}
        />
        {beat.fact && (
          <div
            style={{
              marginTop: 56,
              display: 'inline-block',
              padding: '26px 38px',
              borderRadius: 28,
              background: COLORS.surface,
              border: `3px solid ${COLORS.caption}`,
              boxShadow: `0 0 60px rgba(255, 225, 77, ${0.25 * fact})`,
              fontFamily: DISPLAY_FONT,
              fontWeight: 800,
              fontSize: beat.fact.length > 16 ? 58 : 76,
              color: COLORS.caption,
              opacity: Math.min(1, fact * 1.4),
              transform: `scale(${0.6 + fact * 0.4}) rotate(${(1 - fact) * -4}deg)`,
              transformOrigin: 'left center',
            }}
          >
            {beat.fact}
          </div>
        )}
        <div
          style={{
            marginTop: 44,
            fontFamily: TEXT_FONT,
            fontSize: 32,
            fontWeight: 600,
            color: COLORS.muted,
            opacity: interpolate(frame, [12, 24], [0, 1], { extrapolateRight: 'clamp' }),
          }}
        >
          источник · {beat.source}
        </div>
      </div>
    </AbsoluteFill>
  )
}
