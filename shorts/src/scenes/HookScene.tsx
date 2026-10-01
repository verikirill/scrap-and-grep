import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, SAFE, TEXT_FONT } from '../theme'
import type { Beat } from '../types'
import { VISUAL_STYLE } from '../visuals'
import { Covers } from './Photo'
import { Words } from './Words'

type Props = {
  hook: string
  audience: string
  beats: Pick<Beat, 'kicker' | 'visual' | 'imageSrc'>[]
  durationInFrames: number
}

// One picture on the cover is a coincidence; two or three show what is ahead.
const MIN_COVERS = 2

/** The first seconds: a loud promise of what is coming, over a pulsing ring. */
export function HookScene({ hook, audience, beats, durationInFrames }: Props) {
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
  const fontSize = shown.length > 60 ? 60 : shown.length > 44 ? 72 : shown.length > 28 ? 84 : 96
  // The number or the first word carries the promise; it gets the colour.
  const accentIndex = Math.max(
    0,
    words.findIndex((word) => /\d/.test(word)),
  )
  const covers = beats.flatMap((beat) =>
    beat.imageSrc ? [{ src: beat.imageSrc, color: VISUAL_STYLE[beat.visual].color }] : [],
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
        <Contents beats={beats} />
        {covers.length >= MIN_COVERS && <Covers pictures={covers} />}
      </div>
    </AbsoluteFill>
  )
}

// Chips that fit above the captions in two rows; the rest is counted in "+N".
const MAX_CHIPS = 5

const chipStyle = (color: string, shown: number) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  maxWidth: '100%',
  padding: '10px 18px',
  borderRadius: 999,
  border: `3px solid ${color}`,
  background: `${color}1f`,
  fontFamily: TEXT_FONT,
  fontWeight: 800,
  fontSize: 28,
  letterSpacing: 1,
  textTransform: 'uppercase' as const,
  whiteSpace: 'nowrap' as const,
  color,
  opacity: Math.min(1, shown * 1.5),
  transform: `translateY(${(1 - shown) * 30}px) scale(${0.85 + shown * 0.15})`,
})

/** What the video is about, one chip per news item, like a table of contents. */
function Contents({ beats }: { beats: Pick<Beat, 'kicker' | 'visual'>[] }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const listed = beats.length > MAX_CHIPS ? beats.slice(0, MAX_CHIPS - 1) : beats
  const more = beats.length - listed.length
  const appear = (index: number) =>
    spring({ frame: frame - 8 - index * 5, fps, config: { damping: 13, stiffness: 150 } })
  return (
    <div style={{ marginTop: 56, display: 'flex', flexWrap: 'wrap', gap: 14 }}>
      {listed.map((beat, index) => {
        const style = VISUAL_STYLE[beat.visual]
        const Icon = style.icon
        return (
          <div key={index} style={chipStyle(style.color, appear(index))}>
            <Icon size={30} color={style.color} strokeWidth={2.4} style={{ flex: 'none' }} />
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{beat.kicker}</span>
          </div>
        )
      })}
      {more > 0 && <div style={chipStyle(COLORS.muted, appear(listed.length))}>+{more}</div>}
    </div>
  )
}
