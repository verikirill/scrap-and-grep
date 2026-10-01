import type { LucideIcon } from 'lucide-react'
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, TEXT_FONT } from '../theme'
import { factShape, fitFontSize, formatCount, labelFontSize, severityColor } from '../visuals'
import { PhotoCard, usePicture } from './Photo'

type Props = {
  fact: string | null
  /** The article's picture, shown when the fact is not a number to draw. */
  imageSrc: string | null
  icon: LucideIcon
  color: string
  /** Frames the picture takes to arrive at its value. */
  durationInFrames: number
}

export const VISUAL_SIZE = 280
const RADIUS = 110
const STROKE = 22

// Below this share of the scale an arc is a dot of its round caps; it is not drawn.
const MIN_ARC = 0.005
// Longer than the longest path of the icons used (the newspaper, about 85
// units), or a path would keep a gap at the end.
const ICON_DASH = 120
// Room for the number: inside the square card, inside the ring.
const COUNT_WIDTH = 250
const RING_TEXT_WIDTH = 180

const SEVERITY = [
  [9, 'критическая'],
  [7, 'высокая'],
  [4, 'средняя'],
  [0, 'низкая'],
] as const

function useFill(durationInFrames: number, delay = 6) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const arrive = Math.max(fps, Math.round(durationInFrames * 0.35))
  const eased = interpolate(frame - delay, [0, arrive], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (t) => 1 - (1 - t) ** 3,
  })
  const pop = spring({ frame: frame - delay, fps, config: { damping: 12, stiffness: 140 } })
  return { eased, pop }
}

/** Half a dial from 0 to 10 with a needle: how dangerous a vulnerability is. */
function Gauge({ score, durationInFrames }: { score: number; durationInFrames: number }) {
  const { eased, pop } = useFill(durationInFrames)
  const value = score * eased
  const color = severityColor(value)
  const half = Math.PI * RADIUS
  const angle = -90 + (value / 10) * 180
  const label = SEVERITY.find(([from]) => score >= from)?.[1] ?? ''
  return (
    <div style={{ width: VISUAL_SIZE, height: VISUAL_SIZE, position: 'relative', transform: `scale(${0.8 + pop * 0.2})` }}>
      <svg width={VISUAL_SIZE} height={VISUAL_SIZE} viewBox="-140 -125 280 280">
        <path d={`M ${-RADIUS} 0 A ${RADIUS} ${RADIUS} 0 0 1 ${RADIUS} 0`} fill="none" stroke={COLORS.line} strokeWidth={STROKE} strokeLinecap="round" />
        {value / 10 > MIN_ARC && (
          <path
            d={`M ${-RADIUS} 0 A ${RADIUS} ${RADIUS} 0 0 1 ${RADIUS} 0`}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={half}
            strokeDashoffset={half * (1 - value / 10)}
            style={{ filter: `drop-shadow(0 0 14px ${color})` }}
          />
        )}
        <line x1={0} y1={0} x2={0} y2={-RADIUS + 34} stroke={COLORS.text} strokeWidth={8} strokeLinecap="round" transform={`rotate(${angle})`} />
        <circle r={14} fill={COLORS.text} />
      </svg>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 138, textAlign: 'center', lineHeight: 1 }}>
        <div style={{ fontFamily: DISPLAY_FONT, fontWeight: 800, fontSize: 60, color, fontVariantNumeric: 'tabular-nums' }}>
          {value.toFixed(1)}
        </div>
        <div style={{ marginTop: 10, fontFamily: TEXT_FONT, fontWeight: 700, fontSize: 22, letterSpacing: 2, color: COLORS.muted, textTransform: 'uppercase' }}>
          CVSS
        </div>
        <div style={{ marginTop: 6, fontFamily: TEXT_FONT, fontWeight: 800, fontSize: 24, letterSpacing: 1, color, textTransform: 'uppercase' }}>
          {label}
        </div>
      </div>
    </div>
  )
}

/** A ring filling up to a share. */
function Ring({ value, label, color, durationInFrames }: { value: number; label: string; color: string; durationInFrames: number }) {
  const { eased, pop } = useFill(durationInFrames)
  const circumference = 2 * Math.PI * RADIUS
  const decimals = label.includes(',') || label.includes('.') ? 1 : 0
  const share = (value / 100) * eased
  // Sized by the final value, so the number does not shrink as it fills.
  const fontSize = fitFontSize(`${formatCount(value, decimals)}%`, RING_TEXT_WIDTH, 60)
  return (
    <div style={{ width: VISUAL_SIZE, height: VISUAL_SIZE, position: 'relative', transform: `scale(${0.8 + pop * 0.2})` }}>
      <svg width={VISUAL_SIZE} height={VISUAL_SIZE} viewBox="-140 -140 280 280" style={{ transform: 'rotate(-90deg)' }}>
        <circle r={RADIUS} fill="none" stroke={COLORS.line} strokeWidth={STROKE} />
        {share > MIN_ARC && (
          <circle
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - share)}
            style={{ filter: `drop-shadow(0 0 14px ${color})` }}
          />
        )}
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: DISPLAY_FONT, fontWeight: 800, fontSize, color: COLORS.text, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {formatCount(value * eased, decimals)}%
      </div>
    </div>
  )
}

/** A number counting up to its value, with what it counts underneath. */
function CountUp({ value, decimals, suffix, color, durationInFrames }: { value: number; decimals: number; suffix: string; color: string; durationInFrames: number }) {
  const { eased, pop } = useFill(durationInFrames)
  // Sized by the final value, so the number does not shrink as it counts.
  const fontSize = fitFontSize(formatCount(value, decimals), COUNT_WIDTH, 88)
  return (
    <div style={{ width: VISUAL_SIZE, height: VISUAL_SIZE, display: 'grid', placeContent: 'center', textAlign: 'center', borderRadius: 40, background: COLORS.surface, border: `3px solid ${color}`, boxShadow: `0 0 60px ${color}55`, transform: `scale(${0.8 + pop * 0.2})` }}>
      <div style={{ fontFamily: DISPLAY_FONT, fontWeight: 800, fontSize, lineHeight: 1, color, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {formatCount(value * eased, decimals)}
      </div>
      <div style={{ marginTop: 14, padding: '0 18px', fontFamily: TEXT_FONT, fontWeight: 700, fontSize: 30, lineHeight: 1.15, color: COLORS.text }}>
        {suffix.trim()}
      </div>
    </div>
  )
}

/** The icon of the kind of news, drawn stroke by stroke, with the fact under it if any. */
function IconDraw({ icon: Icon, color, text, durationInFrames }: { icon: LucideIcon; color: string; text: string | null; durationInFrames: number }) {
  const frame = useCurrentFrame()
  const { eased, pop } = useFill(durationInFrames, 2)
  const pulse = (frame % 45) / 45
  // stroke-dasharray is inherited, so setting it on the icon draws every path.
  // The icon fades in over the first strokes: a dash of zero length would
  // still show the dots of its round caps.
  const dash = ICON_DASH
  const circle = text ? 170 : 210
  return (
    <div style={{ width: VISUAL_SIZE, height: VISUAL_SIZE, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
      <div style={{ position: 'relative', width: circle, height: circle, display: 'grid', placeItems: 'center' }}>
        <div style={{ position: 'absolute', inset: -10, borderRadius: '50%', border: `4px solid ${color}`, opacity: 0.6 * (1 - pulse), transform: `scale(${0.8 + pulse * 0.35})` }} />
        <div style={{ width: circle, height: circle, borderRadius: '50%', display: 'grid', placeItems: 'center', background: `${color}1f`, transform: `scale(${0.7 + pop * 0.3})` }}>
          <Icon size={circle * 0.58} color={color} strokeWidth={1.8} style={{ strokeDasharray: dash, strokeDashoffset: dash * (1 - eased), opacity: Math.min(1, eased * 8), filter: `drop-shadow(0 0 16px ${color})` }} />
        </div>
      </div>
      {text && (
        <div style={{ maxWidth: VISUAL_SIZE, padding: '8px 16px', borderRadius: 16, background: COLORS.ink, border: `3px solid ${COLORS.caption}`, fontFamily: DISPLAY_FONT, fontWeight: 800, fontSize: labelFontSize(text, VISUAL_SIZE - 38, 30), lineHeight: 1.15, textAlign: 'center', color: COLORS.caption, opacity: Math.min(1, pop * 1.4) }}>
          {text}
        </div>
      )}
    </div>
  )
}

/**
 * The picture of a news card, chosen by the shape of its fact: a number gets
 * its gauge, ring or counter; otherwise the article's own picture, and the
 * icon of the kind of news when there is none.
 */
export function FactVisual({ fact, imageSrc, icon, color, durationInFrames }: Props) {
  const [picture, onPictureError] = usePicture(imageSrc)
  const shape = fact ? factShape(fact) : null
  if (shape?.kind === 'cvss') {
    return <Gauge score={shape.score} durationInFrames={durationInFrames} />
  }
  if (shape?.kind === 'percent') {
    return <Ring value={shape.value} label={shape.label} color={color} durationInFrames={durationInFrames} />
  }
  if (shape?.kind === 'number') {
    return <CountUp value={shape.value} decimals={shape.decimals} suffix={shape.suffix} color={color} durationInFrames={durationInFrames} />
  }
  const text = shape?.kind === 'text' ? shape.text : null
  if (picture) {
    return <PhotoCard src={picture} icon={icon} color={color} text={text} durationInFrames={durationInFrames} onError={onPictureError} />
  }
  return <IconDraw icon={icon} color={color} text={text} durationInFrames={durationInFrames} />
}
