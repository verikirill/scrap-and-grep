/**
 * The radar behind the cat on the sign-in page: faint rings, a beam that
 * sweeps the circle once in SWEEP_S, and blips that flare as the beam passes
 * them, as the service combs its sources. CSS only (index.css, .auth-radar):
 * transform and opacity, still under "reduce motion".
 */

const SWEEP_S = 12

// Where the finds are: an angle clockwise from the top and a share of the radius.
// The radar is far wider than the side; the finds keep to the part in view.
const BLIPS = [
  { angle: 18, radius: 0.31 },
  { angle: 47, radius: 0.15 },
  { angle: 74, radius: 0.42 },
  { angle: 102, radius: 0.24 },
  { angle: 131, radius: 0.36 },
  { angle: 155, radius: 0.12 },
  { angle: 176, radius: 0.47 },
  { angle: 199, radius: 0.29 },
  { angle: 222, radius: 0.4 },
  { angle: 248, radius: 0.18 },
  { angle: 271, radius: 0.33 },
  { angle: 301, radius: 0.44 },
  { angle: 322, radius: 0.22 },
  { angle: 344, radius: 0.37 },
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
