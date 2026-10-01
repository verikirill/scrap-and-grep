import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, TEXT_FONT } from '../theme'
import { QrCode, useQr } from './QrCode'

type Props = {
  source: string
  date: string | null
  url: string | null
  color: string
  /** Frame the card appears at. */
  from: number
}

/** Where the news comes from, with a QR code that opens the article. */
export function SourceCard({ source, date, url, color, from }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const qr = useQr(url)
  const shown = spring({ frame: frame - from, fps, config: { damping: 14, stiffness: 130 } })
  // A scanner beam runs over the code once, so it reads as "point a camera here".
  const beam = interpolate(frame - from, [8, 38], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 28,
        opacity: Math.min(1, shown * 1.5),
        transform: `translateY(${(1 - shown) * 40}px)`,
      }}
    >
      {qr && (
        <div
          style={{
            position: 'relative',
            flex: 'none',
            padding: qr.padding,
            borderRadius: 24,
            background: '#ffffff',
            boxShadow: `0 0 0 4px ${color}, 0 20px 60px rgba(0, 0, 0, 0.45)`,
            overflow: 'hidden',
          }}
        >
          <QrCode qr={qr} color={COLORS.ink} />
          {beam > 0 && beam < 1 && (
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: qr.padding + beam * qr.size,
                height: 6,
                background: color,
                boxShadow: `0 0 24px 6px ${color}`,
              }}
            />
          )}
        </div>
      )}
      <div style={{ minWidth: 0, fontFamily: TEXT_FONT }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: 3, textTransform: 'uppercase', color }}>Источник</div>
        <div style={{ marginTop: 6, fontSize: 38, fontWeight: 800, lineHeight: 1.1, color: COLORS.text }}>{source}</div>
        {date && <div style={{ marginTop: 8, fontSize: 28, fontWeight: 600, color: COLORS.muted }}>{date}</div>}
        {qr && (
          <div style={{ marginTop: 12, fontSize: 26, fontWeight: 600, lineHeight: 1.2, color: COLORS.muted }}>
            Наведите камеру, чтобы открыть статью
          </div>
        )}
      </div>
    </div>
  )
}
