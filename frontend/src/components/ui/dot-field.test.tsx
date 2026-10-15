import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DotField } from './dot-field'
import DotGrid from './dot-grid'

// The grid itself is WebGL2 and draws nothing in jsdom (below); the field is
// what the app sets on it, so the grid is replaced by a stand-in that records.
vi.mock('./dot-grid', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./dot-grid')>()
  return {
    ...actual,
    default: vi.fn(() => <canvas data-testid="grid" />),
  }
})

const grid = vi.mocked(DotGrid)

describe('DotField', () => {
  it('fixes the grid under the app with quiet settings for a working screen', () => {
    render(<DotField dark={false} />)
    const props = grid.mock.calls.at(-1)?.[0]
    expect(props?.className).toBe('dot-field')
    expect(props?.proximity).toBeLessThanOrEqual(120)
    expect(props?.glow).toBe(0)
    expect(props?.shockStrength).toBeLessThan(2)
  })

  it('keeps the dots grey in both themes, a step off the page and darker under the pointer', () => {
    render(<DotField dark={false} />)
    const light = grid.mock.calls.at(-1)?.[0]
    render(<DotField dark />)
    const dark = grid.mock.calls.at(-1)?.[0]
    expect(light?.baseColor).toBe('#d3d6dc')
    expect(light?.activeColor).toBe('#aeb4bf')
    expect(dark?.baseColor).toBe('#24262b')
    expect(dark?.activeColor).toBe('#3a3e47')
    for (const colour of [light?.activeColor, dark?.activeColor]) {
      expect(colour).toMatch(/^#[0-9a-f]{6}$/)
    }
  })
})

describe('DotGrid without WebGL2', () => {
  it('renders a canvas and draws nothing, as in jsdom and old browsers', async () => {
    const { default: RealDotGrid } =
      await vi.importActual<typeof import('./dot-grid')>('./dot-grid')
    const { container } = render(<RealDotGrid className="dot-field" />)
    const canvas = container.querySelector<HTMLCanvasElement>('canvas.dot-grid__canvas')
    expect(canvas).not.toBeNull()
    expect(container.querySelector('.dot-grid.dot-field')).not.toBeNull()
    // jsdom has no WebGL2: getContext answers null, and the grid stops there.
    expect(canvas?.getContext('webgl2')).toBeNull()
  })
})
