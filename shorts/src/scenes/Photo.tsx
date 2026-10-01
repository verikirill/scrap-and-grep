import type { LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, alpha } from '../theme'
import { labelFontSize } from '../visuals'

// The pictures come from the render server itself and are checked to be
// pictures, but a browser may still fail to decode one. <Img> would then
// cancel the whole render; the scene draws itself without it instead.
/** The picture while it works, then null. */
export function usePicture(src: string | null): [string | null, () => void] {
  const [isBroken, setBroken] = useState(false)
  return [isBroken ? null : src, () => setBroken(true)]
}

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const

/**
 * The article's own picture behind the whole news item: blurred, so a small
 * picture stretched to the frame does not show its pixels and the text some
 * sites draw on their pictures does not compete with the title; dimmed, so
 * the text above it stays readable; drifting slowly the whole time.
 */
export function Backdrop({ src, number, durationInFrames }: { src: string; number: number; durationInFrames: number }) {
  const frame = useCurrentFrame()
  const [picture, onError] = usePicture(src)
  if (!picture) {
    return null
  }
  const progress = Math.min(1, frame / durationInFrames)
  const appear = interpolate(frame, [0, 12], [0, 1], clamp)
  // Every other picture drifts the other way, so a cut reads as a cut.
  const direction = number % 2 === 0 ? -1 : 1
  return (
    <AbsoluteFill style={{ opacity: appear, overflow: 'hidden', backgroundColor: COLORS.ink }}>
      <Img
        src={picture}
        onError={onError}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${1.12 + progress * 0.12}) translateX(${direction * progress * 28}px)`,
          filter: 'blur(14px) saturate(1.15)',
        }}
      />
      <AbsoluteFill
        style={{
          background: `linear-gradient(180deg, ${alpha(COLORS.ink, 0.8)} 0%, ${alpha(COLORS.ink, 0.68)} 32%, ${alpha(COLORS.ink, 0.86)} 60%, ${alpha(COLORS.ink, 0.97)} 100%)`,
        }}
      />
    </AbsoluteFill>
  )
}

export const PHOTO_WIDTH = 330
export const PHOTO_HEIGHT = 280
// Room for the fact on the picture: the card less its margins and padding.
const FACT_WIDTH = PHOTO_WIDTH - 64

type CardProps = {
  src: string
  icon: LucideIcon
  color: string
  /** An identifier or a date worth showing over the picture. */
  text: string | null
  durationInFrames: number
  onError: () => void
}

/** The picture of the news, sharp, in the place of the icon when the news has no number to draw. */
export function PhotoCard({ src, icon: Icon, color, text, durationInFrames, onError }: CardProps) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const pop = spring({ frame: frame - 4, fps, config: { damping: 14, stiffness: 140 } })
  const progress = Math.min(1, frame / durationInFrames)
  return (
    <div
      style={{
        position: 'relative',
        flex: 'none',
        width: PHOTO_WIDTH,
        height: PHOTO_HEIGHT,
        borderRadius: 40,
        overflow: 'hidden',
        border: `4px solid ${color}`,
        background: COLORS.surface,
        boxShadow: `0 0 60px ${alpha(color, 0.33)}`,
        opacity: Math.min(1, pop * 1.5),
        transform: `scale(${0.85 + pop * 0.15})`,
      }}
    >
      <Img
        src={src}
        onError={onError}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${1.04 + progress * 0.12})` }}
      />
      <div
        style={{
          position: 'absolute',
          left: 16,
          top: 16,
          width: 60,
          height: 60,
          borderRadius: 20,
          display: 'grid',
          placeItems: 'center',
          background: alpha(COLORS.ink, 0.85),
        }}
      >
        <Icon size={34} color={color} strokeWidth={2.4} />
      </div>
      {text && (
        <div
          style={{
            position: 'absolute',
            left: 14,
            right: 14,
            bottom: 14,
            padding: '8px 14px',
            borderRadius: 16,
            background: COLORS.ink,
            border: `3px solid ${COLORS.caption}`,
            fontFamily: DISPLAY_FONT,
            fontWeight: 800,
            fontSize: labelFontSize(text, FACT_WIDTH, 28),
            lineHeight: 1.15,
            textAlign: 'center',
            color: COLORS.caption,
          }}
        >
          {text}
        </div>
      )}
    </div>
  )
}

const COVER_GAP = 20
const COVER_HEIGHT = 220

/**
 * Up to three pictures of the news ahead, on the first frame: the frame the
 * platforms show before anyone presses play.
 */
export function Covers({ pictures }: { pictures: { src: string; color: string }[] }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <div style={{ marginTop: 44, display: 'flex', gap: COVER_GAP }}>
      {pictures.slice(0, 3).map((picture, index) => (
        <Cover key={picture.src} {...picture} settle={spring({ frame: frame - index * 4, fps, config: { damping: 14 } })} />
      ))}
    </div>
  )
}

function Cover({ src, color, settle }: { src: string; color: string; settle: number }) {
  const [picture, onError] = usePicture(src)
  if (!picture) {
    return null
  }
  // Visible from the first frame; the spring only settles it into place.
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        height: COVER_HEIGHT,
        borderRadius: 28,
        overflow: 'hidden',
        border: `3px solid ${color}`,
        boxShadow: `0 18px 50px ${alpha(COLORS.ink, 0.6)}`,
        transform: `translateY(${(1 - settle) * 24}px) scale(${0.94 + settle * 0.06})`,
      }}
    >
      <Img src={picture} onError={onError} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  )
}
