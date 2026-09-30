import { createTikTokStyleCaptions } from '@remotion/captions'
import type { Caption, TikTokPage } from '@remotion/captions'
import { useMemo } from 'react'
import { AbsoluteFill, Sequence, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { COLORS, SAFE, TEXT_FONT } from '../theme'
import type { Word } from '../types'

// A page holds what is said in about a second: two to four words, the
// rhythm viewers of short videos are used to.
const PAGE_MS = 1000

function CaptionPage({ page }: { page: TikTokPage }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const nowMs = page.startMs + (frame / fps) * 1000
  const enter = spring({ frame, fps, config: { damping: 14, stiffness: 220 } })

  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center' }}>
      <div
        style={{
          marginBottom: SAFE.bottom + 40,
          maxWidth: 960,
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          // Words are separate boxes (the active one grows), so the space
          // between them is a gap rather than a character.
          columnGap: '0.32em',
          fontFamily: TEXT_FONT,
          fontWeight: 900,
          fontSize: 76,
          lineHeight: 1.15,
          textTransform: 'uppercase',
          transform: `scale(${0.85 + enter * 0.15})`,
        }}
      >
        {page.tokens.map((token, index) => {
          const isActive = token.fromMs <= nowMs && token.toMs > nowMs
          return (
            <span
              key={`${token.fromMs}-${index}`}
              style={{
                display: 'inline-block',
                color: isActive ? COLORS.caption : COLORS.text,
                // A thick outline keeps captions readable on any background.
                WebkitTextStroke: `14px ${COLORS.ink}`,
                paintOrder: 'stroke fill',
                // A lift rather than a scale: scaling a long word would eat
                // the gap to its neighbours.
                transform: `translateY(${isActive ? -8 : 0}px)`,
              }}
            >
              {token.text.trim()}
            </span>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}

/** Word-by-word captions with the spoken word lit up, as in short videos. */
export function Captions({ words }: { words: Word[] }) {
  const { fps } = useVideoConfig()
  const pages = useMemo(() => {
    const captions: Caption[] = words.map((word, index) => ({
      // Pages are split on spaces, so every word but the first carries one.
      text: index === 0 ? word.text : ` ${word.text}`,
      startMs: word.startMs,
      endMs: word.endMs,
      timestampMs: null,
      confidence: null,
    }))
    return createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: PAGE_MS,
      breakOnSilenceAfterMilliseconds: 250,
    }).pages
  }, [words])

  return (
    <>
      {pages.map((page, index) => {
        const next = pages[index + 1]
        const from = Math.round((page.startMs / 1000) * fps)
        const until = next ? (next.startMs / 1000) * fps : from + ((page.durationMs + 400) / 1000) * fps
        const duration = Math.max(1, Math.round(until) - from)
        return (
          <Sequence key={page.startMs} from={from} durationInFrames={duration} layout="none">
            <CaptionPage page={page} />
          </Sequence>
        )
      })}
    </>
  )
}
