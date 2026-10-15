import { motion } from 'motion/react'
import type { TargetAndTransition, Transition } from 'motion/react'
import { useId } from 'react'
import { cn } from '../lib/utils'
import { useMediaQuery } from '../lib/useMediaQuery'

/**
 * What the cat is doing: looking through the news, holding up what it found,
 * shrugging at an empty place, upset by a failure, or waiting its turn.
 */
export type MascotPose = 'searching' | 'found' | 'empty' | 'error' | 'waiting'

type Props = {
  pose: MascotPose
  /** Width and height in pixels. */
  size?: number
  /** Said for the picture; without it the cat is decoration and hidden from screen readers. */
  label?: string
  /** A soft accent disc behind the cat, for empty places that need a picture. */
  hasBackdrop?: boolean
  className?: string
}

const LOOP: Transition = { repeat: Infinity, ease: 'easeInOut' }

type Loop = TargetAndTransition | undefined

/** Loops of each pose; a still pose (reduced motion) skips them all. */
function loops(pose: MascotPose): Record<
  'tail' | 'body' | 'head' | 'blink' | 'pupils' | 'glass' | 'float' | 'clockHand',
  Loop
> & {
  sparkle: (delay: number) => Loop
} {
  const isSearching = pose === 'searching'
  const tail: Transition = { duration: pose === 'waiting' ? 1.1 : 2.6, ...LOOP }
  return {
    tail: pose === 'error' ? undefined : { rotate: [-6, 9, -6], transition: tail },
    body:
      pose === 'found'
        ? { y: [0, -4, 0, 0], transition: { duration: 1.6, times: [0, 0.2, 0.4, 1], ...LOOP } }
        : pose === 'error'
          ? {
              x: [0, -1.5, 1.5, -1, 0],
              transition: { duration: 0.5, repeatDelay: 1.8, repeat: Infinity },
            }
          : { y: [0, -1.2, 0], transition: { duration: 3, ...LOOP } },
    head: isSearching ? { rotate: [3, -4, 3], transition: { duration: 2.4, ...LOOP } } : undefined,
    blink: {
      scaleY: [1, 1, 0.1, 1],
      transition: { duration: 4.2, times: [0, 0.9, 0.95, 1], repeat: Infinity },
    },
    pupils: isSearching
      ? { x: [1.6, -1.8, 1.6], transition: { duration: 2.4, ...LOOP } }
      : undefined,
    glass: isSearching
      ? { x: [0, -22, 0], y: [0, -5, 0], transition: { duration: 2.4, ...LOOP } }
      : undefined,
    float: { y: [0, -3, 0], transition: { duration: 1.8, ...LOOP } },
    sparkle: (delay: number) => ({
      scale: [0, 1, 0],
      opacity: [0, 1, 0],
      transition: { duration: 1.6, delay, repeat: Infinity, repeatDelay: 0.4 },
    }),
    clockHand: { rotate: [0, 360], transition: { duration: 3, repeat: Infinity, ease: 'linear' } },
  }
}

/**
 * The cat of Scrap&Grep: the black cat of the logo, with its magnifier. Drawn
 * in SVG and coloured by the theme (--mascot-* in index.css), so it is a few
 * hundred bytes and reads on light and dark surfaces alike. Only transforms
 * and opacity move; with "reduce motion" on the pose stands still.
 */
export function Mascot({ pose, size = 96, label, hasBackdrop = false, className }: Props) {
  const isStill = useMediaQuery('(prefers-reduced-motion: reduce)')
  const id = useId().replace(/:/g, '')
  const fur = `url(#fur-${id})`
  const loop = loops(pose)
  // A still cat gets no animate props at all: nothing is scheduled.
  const move = <T,>(value: T): T | undefined => (isStill ? undefined : value)

  const isHappy = pose === 'found'
  const isUpset = pose === 'error'
  const hasGlass = pose !== 'found'
  // Where the pupils look: up at the clock or the question, ahead otherwise.
  const pupilY = pose === 'waiting' || pose === 'empty' ? -2 : 0
  const pupilX = pose === 'empty' ? 2 : 0

  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      data-pose={pose}
      data-motion={isStill ? 'still' : 'live'}
      className={cn('mascot shrink-0 overflow-visible', className)}
    >
      <defs>
        <radialGradient id={`fur-${id}`} cx="38%" cy="28%" r="80%">
          <stop offset="0%" style={{ stopColor: 'var(--mascot-fur-light)' }} />
          <stop offset="70%" style={{ stopColor: 'var(--mascot-fur)' }} />
        </radialGradient>
      </defs>
      {hasBackdrop && <circle cx="60" cy="64" r="54" className="fill-accent-soft" />}
      <ellipse cx="60" cy="109" rx="30" ry="4" fill="currentColor" opacity="0.12" />

      <motion.g animate={move(loop.body)}>
        {/* The tail, behind the body, swinging from its root. */}
        <motion.path
          d="M80 102 C100 104 110 86 102 72 C99 66 93 66 94 72"
          fill="none"
          stroke="var(--mascot-fur)"
          strokeWidth="8"
          strokeLinecap="round"
          style={{ originX: 0, originY: 1 }}
          animate={move(loop.tail)}
        />
        <path
          d="M38 106 C33 86 38 66 60 64 C82 66 87 86 82 106 Q60 111 38 106 Z"
          fill={fur}
          className="mascot-rim"
        />
        <ellipse cx="48" cy="106" rx="8" ry="4.5" fill="var(--mascot-fur)" />
        <ellipse cx="72" cy="106" rx="8" ry="4.5" fill="var(--mascot-fur)" />

        <motion.g style={{ originX: 0.5, originY: 0.9 }} animate={move(loop.head)}>
          <g transform={isUpset ? 'rotate(-16 47 34)' : undefined}>
            <path d="M36 40 Q32 17 39 12 Q50 18 57 28 Z" fill={fur} className="mascot-rim" />
            <path d="M40 33 Q38 21 41 18 Q47 22 51 28 Z" fill="var(--mascot-ear)" />
          </g>
          <g transform={isUpset ? 'rotate(16 73 34)' : undefined}>
            <path d="M84 40 Q88 17 81 12 Q70 18 63 28 Z" fill={fur} className="mascot-rim" />
            <path d="M80 33 Q82 21 79 18 Q73 22 69 28 Z" fill="var(--mascot-ear)" />
          </g>
          <ellipse cx="60" cy="45" rx="27" ry="21" fill={fur} className="mascot-rim" />

          {isHappy ? (
            <g fill="none" stroke="var(--mascot-eye)" strokeWidth="2.8" strokeLinecap="round">
              <path d="M44 46 Q50 38 56 46" />
              <path d="M64 46 Q70 38 76 46" />
            </g>
          ) : (
            <motion.g style={{ originX: 0.5, originY: 0.5 }} animate={move(loop.blink)}>
              <ellipse cx="50" cy="45" rx="6.2" ry={isUpset ? 5.5 : 6.6} fill="var(--mascot-eye)" />
              <ellipse cx="70" cy="45" rx="6.2" ry={isUpset ? 5.5 : 6.6} fill="var(--mascot-eye)" />
              <motion.g animate={move(loop.pupils)}>
                <g transform={`translate(${pupilX} ${pupilY})`} fill="var(--mascot-pupil)">
                  {isUpset ? (
                    <>
                      <circle cx="50" cy="46" r="2.3" />
                      <circle cx="70" cy="46" r="2.3" />
                    </>
                  ) : (
                    <>
                      <ellipse cx="50" cy="45.5" rx="2.3" ry="4.6" />
                      <ellipse cx="70" cy="45.5" rx="2.3" ry="4.6" />
                      <circle cx="51.6" cy="43" r="1.2" fill="var(--mascot-eye)" />
                      <circle cx="71.6" cy="43" r="1.2" fill="var(--mascot-eye)" />
                    </>
                  )}
                </g>
              </motion.g>
            </motion.g>
          )}
          {isUpset && (
            <g stroke="var(--mascot-eye)" strokeWidth="2" strokeLinecap="round">
              <path d="M43 37 L55 34" />
              <path d="M77 37 L65 34" />
            </g>
          )}

          <path d="M57.6 52 L62.4 52 L60 54.8 Z" fill="var(--mascot-ear)" />
          <path
            d={
              isUpset
                ? 'M55.5 59 Q60 55.5 64.5 59'
                : isHappy
                  ? 'M55 56 Q60 62 65 56'
                  : 'M56 56.5 Q58 58.5 60 56.5 Q62 58.5 64 56.5'
            }
            fill="none"
            stroke="var(--mascot-eye)"
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity="0.85"
          />
          <g stroke="var(--mascot-eye)" strokeWidth="1" strokeLinecap="round" opacity="0.35">
            <path d="M35 51 L47 53.5" />
            <path d="M35 56.5 L47 56.5" />
            <path d="M85 51 L73 53.5" />
            <path d="M85 56.5 L73 56.5" />
          </g>
        </motion.g>

        {hasGlass && (
          // The pose sets the outer group, the loop moves the inner one: a CSS
          // transform from motion would replace an SVG transform on the same node.
          <g
            transform={
              pose === 'empty'
                ? 'rotate(72 72 94)'
                : pose === 'waiting'
                  ? 'translate(0 4)'
                  : undefined
            }
          >
            <motion.g animate={move(loop.glass)}>
              <path
                d="M70 93 L79 84"
                stroke="var(--accent)"
                strokeWidth="5.5"
                strokeLinecap="round"
              />
              <circle
                cx="87"
                cy="76"
                r="11"
                fill="var(--mascot-glass)"
                stroke="var(--accent)"
                strokeWidth="4.5"
              />
              {isUpset ? (
                <path
                  d="M83 68 L88 75 L84 79 L91 85"
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
              ) : (
                <path
                  d="M81 72 Q83 68.5 87.5 68"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                  strokeLinecap="round"
                  opacity="0.85"
                />
              )}
              <ellipse cx="69.5" cy="93.5" rx="6.5" ry="5.5" fill={fur} className="mascot-rim" />
            </motion.g>
          </g>
        )}

        {isHappy && (
          <g>
            <g transform="rotate(8 86 76)">
              <rect x="74" y="58" width="25" height="31" rx="3.5" fill="var(--mascot-paper)" />
              <rect x="78" y="64" width="6" height="6" rx="1.5" fill="var(--accent)" />
              <rect x="86" y="65" width="9" height="2" rx="1" fill="var(--mascot-ink)" />
              <rect x="86" y="68.5" width="6" height="1.6" rx="0.8" fill="var(--accent)" />
              <rect x="78" y="74" width="17" height="2" rx="1" fill="var(--mascot-ink)" />
              <rect x="78" y="78" width="12" height="2" rx="1" fill="var(--mascot-ink)" />
              <circle cx="96" cy="86" r="6.5" fill="var(--success)" />
              <path
                d="M93 86 L95.3 88.2 L99 84"
                fill="none"
                stroke="white"
                strokeWidth="1.9"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
            <ellipse cx="73" cy="88" rx="6.5" ry="5.5" fill={fur} className="mascot-rim" />
          </g>
        )}
      </motion.g>

      {isHappy &&
        [
          { x: 98, y: 34, s: 1, d: 0 },
          { x: 20, y: 46, s: 0.75, d: 0.5 },
          { x: 106, y: 56, s: 0.6, d: 0.9 },
        ].map((spark) => (
          <motion.path
            key={spark.x}
            d={`M${spark.x} ${spark.y - 6 * spark.s} L${spark.x + 1.6 * spark.s} ${spark.y - 1.6 * spark.s} L${spark.x + 6 * spark.s} ${spark.y} L${spark.x + 1.6 * spark.s} ${spark.y + 1.6 * spark.s} L${spark.x} ${spark.y + 6 * spark.s} L${spark.x - 1.6 * spark.s} ${spark.y + 1.6 * spark.s} L${spark.x - 6 * spark.s} ${spark.y} L${spark.x - 1.6 * spark.s} ${spark.y - 1.6 * spark.s} Z`}
            fill="var(--warning)"
            animate={move(loop.sparkle(spark.d))}
          />
        ))}

      {pose === 'empty' && (
        <motion.text
          x="94"
          y="30"
          fontSize="22"
          fontWeight="800"
          fill="var(--accent)"
          fontFamily="inherit"
          animate={move(loop.float)}
        >
          ?
        </motion.text>
      )}

      {isUpset && (
        <motion.path
          d="M88 24 C88 24 83 31 83 34 A5 5 0 0 0 93 34 C93 31 88 24 88 24 Z"
          fill="var(--mascot-glass)"
          stroke="var(--accent)"
          strokeWidth="1.4"
          animate={move(loop.float)}
        />
      )}

      {pose === 'waiting' && (
        <motion.g animate={move(loop.float)}>
          <circle
            cx="96"
            cy="26"
            r="11"
            fill="var(--mascot-paper)"
            stroke="var(--accent)"
            strokeWidth="2.5"
          />
          <path
            d="M96 26 L96 20"
            stroke="var(--mascot-ink)"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <motion.path
            d="M96 26 L101 26"
            stroke="var(--accent)"
            strokeWidth="2"
            strokeLinecap="round"
            style={{ originX: 0, originY: 0.5 }}
            animate={move(loop.clockHand)}
          />
        </motion.g>
      )}
    </svg>
  )
}
