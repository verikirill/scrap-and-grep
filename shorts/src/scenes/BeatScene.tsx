import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, DISPLAY_FONT, SAFE, TEXT_FONT } from '../theme'
import type { Beat } from '../types'
import { VISUAL_STYLE } from '../visuals'
import { FactVisual } from './FactVisual'
import { Backdrop } from './Photo'
import { Points } from './Points'
import { SourceCard } from './SourceCard'
import { Words } from './Words'

type Props = {
  beat: Beat
  number: number
  durationInFrames: number
}

/**
 * One news item: what kind of news it is, the headline, a picture of its key
 * number or the article's own picture, the facts ticked off one by one and
 * the source with a QR code to the article, over the article's picture. The
 * text slides in from the right; everything fades out into the next item.
 */
export function BeatScene({ beat, number, durationInFrames }: Props) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const style = VISUAL_STYLE[beat.visual]
  const Icon = style.icon
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 120 } })
  const exit = interpolate(frame, [durationInFrames - 7, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  const titleWords = beat.title.split(/\s+/).filter(Boolean)
  // Titles run up to about 90 characters; long ones step down so the picture,
  // the facts and the source still fit above the captions.
  const titleSize = beat.title.length > 70 ? 54 : beat.title.length > 48 ? 62 : 72

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      {beat.imageSrc && <Backdrop src={beat.imageSrc} number={number} durationInFrames={durationInFrames} />}
      <AbsoluteFill style={{ transform: `translateX(${(1 - enter) * 140}px)` }}>
        <div
          style={{
            position: 'absolute',
            top: SAFE.top + 110,
            left: SAFE.side,
            right: SAFE.side,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              fontFamily: TEXT_FONT,
              fontWeight: 800,
              fontSize: 34,
              letterSpacing: 3,
              textTransform: 'uppercase',
              color: style.color,
            }}
          >
            <span style={{ padding: '6px 16px', borderRadius: 14, background: style.color, color: COLORS.ink }}>
              {String(number).padStart(2, '0')}
            </span>
            <Icon size={40} color={style.color} strokeWidth={2.4} />
            {beat.kicker}
          </div>
          <Words
            text={beat.title}
            delay={5}
            stagger={3}
            accent={{ indexes: [titleWords.length - 1], color: COLORS.spark }}
            style={{
              marginTop: 20,
              fontFamily: DISPLAY_FONT,
              fontWeight: 700,
              fontSize: titleSize,
              lineHeight: 1.12,
              color: COLORS.text,
            }}
          />
          <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 36 }}>
            <FactVisual
              fact={beat.fact}
              imageSrc={beat.imageSrc}
              icon={Icon}
              color={style.color}
              durationInFrames={durationInFrames}
            />
            {beat.points.length > 0 && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <Points points={beat.points} color={style.color} durationInFrames={durationInFrames} />
              </div>
            )}
          </div>
          <div style={{ marginTop: 24 }}>
            <SourceCard
              source={beat.source}
              date={beat.date}
              url={beat.url}
              color={style.color}
              from={Math.round(durationInFrames * 0.16)}
            />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}
