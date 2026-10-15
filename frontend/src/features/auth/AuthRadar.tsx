/**
 * The radar behind the cat on the sign-in page: faint rings, a beam that
 * sweeps the circle once in SWEEP_S, and blips that flare as the beam passes
 * them, as the service combs its sources. CSS only (index.css, .auth-radar):
 * transform and opacity, still under "reduce motion".
 */

const SWEEP_S = 12

// Where the finds are: an angle clockwise from the top and a share of the radius.
const BLIPS = [
  { angle: 28, radius: 0.62 },
  { angle: 74, radius: 0.34 },
  { angle: 131, radius: 0.83 },
  { angle: 168, radius: 0.5 },
  { angle: 222, radius: 0.71 },
  { angle: 263, radius: 0.27 },
  { angle: 301, radius: 0.9 },
  { angle: 338, radius: 0.46 },
]

export function AuthRadar() {
  return (
    <div aria-hidden className="auth-radar">
      <div className="auth-radar__rings" />
      <div className="auth-radar__sweep" />
      {BLIPS.map(({ angle, radius }) => {
        const rad = (angle * Math.PI) / 180
        return (
          <span
            key={angle}
            className="auth-radar__blip"
            style={{
              left: `${50 + 50 * radius * Math.sin(rad)}%`,
              top: `${50 - 50 * radius * Math.cos(rad)}%`,
              // Lit the moment the beam reaches its angle, every turn.
              animationDelay: `${(angle / 360) * SWEEP_S}s`,
            }}
          />
        )
      })}
    </div>
  )
}
