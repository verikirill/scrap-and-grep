import { motion, useReducedMotion } from 'motion/react'

const SWEEP_SECONDS = 9

// Topics as blips: angle in degrees clockwise from the top, distance from the
// centre as a share of the radius.
const BLIPS = [
  { label: 'SCADA', angle: 38, distance: 0.52 },
  { label: 'CVE', angle: 96, distance: 0.78 },
  { label: '187-ФЗ', angle: 151, distance: 0.44 },
  { label: 'Kubernetes', angle: 214, distance: 0.7 },
  { label: 'МЭК 61850', angle: 268, distance: 0.56 },
  { label: 'LLM', angle: 322, distance: 0.82 },
]

function position(angle: number, distance: number) {
  const radians = ((angle - 90) * Math.PI) / 180
  return {
    left: `${50 + Math.cos(radians) * distance * 50}%`,
    top: `${50 + Math.sin(radians) * distance * 50}%`,
  }
}

/**
 * The product in one picture: a sweep passes over topics and each one lights
 * up as it is found. Decorative, so it is hidden from assistive technology.
 * Only transforms and opacity move; with "reduce motion" on it stands still.
 */
export function RadarVisual() {
  // The opacity pulse is not a transform, so MotionConfig would keep it
  // running under "reduce motion"; here everything stops instead.
  const isStill = useReducedMotion() ?? false
  return (
    <div aria-hidden className="relative aspect-square w-full max-w-[26rem]">
      {[1, 0.74, 0.48, 0.22].map((scale) => (
        <span
          key={scale}
          className="absolute inset-0 m-auto rounded-full border border-white/10"
          style={{ width: `${scale * 100}%`, height: `${scale * 100}%` }}
        />
      ))}
      <span className="absolute inset-x-0 top-1/2 h-px bg-white/[0.07]" />
      <span className="absolute inset-y-0 left-1/2 w-px bg-white/[0.07]" />

      <motion.span
        className="absolute inset-0 rounded-full"
        style={{
          background:
            'conic-gradient(from 0deg, transparent 0deg, transparent 300deg, rgb(125 155 255 / 0.32) 358deg, transparent 360deg)',
        }}
        animate={isStill ? undefined : { rotate: 360 }}
        transition={{ duration: SWEEP_SECONDS, repeat: Infinity, ease: 'linear' }}
      />

      {BLIPS.map((blip) => (
        <span
          key={blip.label}
          className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-2"
          style={position(blip.angle, blip.distance)}
        >
          <motion.span
            className="size-2 rounded-full bg-[#f5b54a]"
            initial={{ opacity: 0.25, scale: 0.8 }}
            animate={
              isStill ? { opacity: 0.8 } : { opacity: [0.25, 1, 0.25], scale: [0.8, 1.35, 0.8] }
            }
            transition={{
              duration: 2.4,
              repeat: Infinity,
              repeatDelay: SWEEP_SECONDS - 2.4,
              // The blip answers the sweep: it lights up when the beam gets to it.
              delay: (blip.angle / 360) * SWEEP_SECONDS,
              ease: 'easeOut',
            }}
          />
          <span className="text-[11px] font-medium tracking-wide whitespace-nowrap text-white/55">
            {blip.label}
          </span>
        </span>
      ))}
      <span className="absolute inset-0 m-auto size-2.5 rounded-full bg-[#7d9bff] shadow-[0_0_0_6px_rgb(125_155_255_/_0.15)]" />
    </div>
  )
}
