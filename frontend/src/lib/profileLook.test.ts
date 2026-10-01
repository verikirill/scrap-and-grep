import { describe, expect, it } from 'vitest'
import { colorOf, hueAndChroma, isCustomColor, profileColors } from './profileLook'

describe('profileColors', () => {
  it('gives a colour of ones own the tones of the palette colours in both themes', () => {
    const { background, color } = profileColors('#1e9c8a')
    // Tile at tone 90 in the light theme and 30 in the dark one, the icon the other way round.
    expect(background).toMatch(/^light-dark\(#[0-9a-f]{6}, #[0-9a-f]{6}\)$/)
    const [lightTile, darkTile] = background.match(/#[0-9a-f]{6}/g) ?? []
    const [lightIcon, darkIcon] = color.match(/#[0-9a-f]{6}/g) ?? []
    expect(lightTile).toBe(darkIcon)
    expect(darkTile).toBe(lightIcon)
  })

  it('lets nothing but a palette key or a hex code into a style', () => {
    for (const value of ['red;background:url(x)', '#1E9C8A', '#12abef00', 'url(x)', null]) {
      expect(isCustomColor(value)).toBe(false)
      expect(profileColors(value)).toEqual({
        background: 'var(--md-tag-blue)',
        color: 'var(--md-on-tag-blue)',
      })
    }
    expect(profileColors('teal').background).toBe('var(--md-tag-teal)')
  })
})

describe('the custom picker', () => {
  it('reads back the hue and colourfulness it was set to', () => {
    const { hue, chroma } = hueAndChroma(colorOf(150, 40))
    expect(Math.abs(hue - 150)).toBeLessThanOrEqual(2)
    expect(Math.abs(chroma - 40)).toBeLessThanOrEqual(2)
  })
})
