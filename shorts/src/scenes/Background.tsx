import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, alpha } from '../theme'

/**
 * Night sky of the product: two slow colour clouds, a faint grid and a radar
 * sweep. Everything moves with the frame number only, so every render of the
 * same props gives the same picture.
 */
export function Background() {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const t = frame / fps
  const cloudA = { x: 30 + Math.sin(t * 0.35) * 18, y: 24 + Math.cos(t * 0.27) * 10 }
  const cloudB = { x: 72 + Math.cos(t * 0.31) * 16, y: 70 + Math.sin(t * 0.23) * 12 }

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.ink, overflow: 'hidden' }}>
      <AbsoluteFill
        style={{
          background: [
            `radial-gradient(circle at ${cloudA.x}% ${cloudA.y}%, ${alpha(COLORS.accent, 0.28)}, transparent 42%)`,
            `radial-gradient(circle at ${cloudB.x}% ${cloudB.y}%, ${alpha(COLORS.spark, 0.16)}, transparent 40%)`,
          ].join(','),
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${COLORS.line} 1px, transparent 1px), linear-gradient(90deg, ${COLORS.line} 1px, transparent 1px)`,
          backgroundSize: '90px 90px',
          maskImage: 'radial-gradient(circle at 50% 45%, black 20%, transparent 75%)',
          opacity: 0.55,
        }}
      />
      <div
        style={{
          position: 'absolute',
          // Larger than the frame, so its round edge is never seen.
          width: 2800,
          height: 2800,
          left: 540 - 1400,
          top: 900 - 1400,
          borderRadius: '50%',
          background:
            `conic-gradient(from 0deg, transparent 0deg, transparent 310deg, ${alpha(COLORS.accent, 0.14)} 358deg, transparent 360deg)`,
          transform: `rotate(${t * 40}deg)`,
        }}
      />
    </AbsoluteFill>
  )
}
