import { describe, expect, it } from 'vitest'
import { hexToOklch } from './oklch'
import { colorOf, hueAndChroma, isCustomColor, profileColors } from './profileLook'

describe('profileColors', () => {
  it('gives a colour of ones own a light tile with a dark icon, and the reverse in the dark theme', () => {
    const { background, color } = profileColors('#1e9c8a')
    expect(background).toMatch(/^light-dark\(#[0-9a-f]{6}, #[0-9a-f]{6}\)$/)
    const [lightTile, darkTile] = (background.match(/#[0-9a-f]{6}/g) ?? []).map(hexToOklch)
    const [lightIcon, darkIcon] = (color.match(/#[0-9a-f]{6}/g) ?? []).map(hexToOklch)
    expect(lightTile.l - lightIcon.l).toBeGreaterThan(0.4)
    expect(darkIcon.l - darkTile.l).toBeGreaterThan(0.4)
    // The tones keep the colour's hue.
    expect(Math.abs(lightTile.h - hexToOklch('#1e9c8a').h)).toBeLessThan(6)
  })

  it('lets nothing but a palette key or a hex code into a style', () => {
    for (const value of ['red;background:url(x)', '#1E9C8A', '#12abef00', 'url(x)', null]) {
      expect(isCustomColor(value)).toBe(false)
      expect(profileColors(value)).toEqual({
        background: 'var(--tag-blue)',
        color: 'var(--on-tag-blue)',
      })
    }
    expect(profileColors('teal').background).toBe('var(--tag-teal)')
  })
})

describe('the custom picker', () => {
  it('reads back the hue and colourfulness it was set to', () => {
    const { hue, chroma } = hueAndChroma(colorOf(150, 40))
    expect(Math.abs(hue - 150)).toBeLessThanOrEqual(2)
    expect(Math.abs(chroma - 40)).toBeLessThanOrEqual(2)
  })
})
