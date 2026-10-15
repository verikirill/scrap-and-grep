import DotGrid from './dot-grid'

// The dots sit a step off the page colour and darken a touch under the pointer,
// which nudges them aside; a click sends a faint ring through them. Quiet on
// purpose: it is a working screen, not a landing page. Hex, because the grid parses only
// that: the theme tokens are oklch.
const LIGHT = { baseColor: '#d3d6dc', activeColor: '#aeb4bf' }
const DARK = { baseColor: '#24262b', activeColor: '#3a3e47' }

/** The sprung dot grid behind the app, fixed under every card (index.css). */
export function DotField({ dark }: { dark: boolean }) {
  return (
    <DotGrid
      className="dot-field"
      dotSize={3}
      gap={22}
      proximity={100}
      strength={0.3}
      shockRadius={180}
      shockStrength={1.2}
      swell={0.25}
      stretch={0.1}
      glow={0}
      {...(dark ? DARK : LIGHT)}
    />
  )
}
