import { render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setMediaQueries } from '../../test/browser'
import { DottedVeil } from './dotted-veil'

// jsdom has no WebGL: a stand-in records what the veil asks of the context.
function fakeGl() {
  const calls = { uniform3f: [] as number[][], draws: 0, lost: false }
  const gl = {
    VERTEX_SHADER: 1,
    FRAGMENT_SHADER: 2,
    ARRAY_BUFFER: 3,
    STATIC_DRAW: 4,
    FLOAT: 5,
    TRIANGLES: 6,
    LINK_STATUS: 7,
    createShader: () => ({}),
    shaderSource: () => {},
    compileShader: () => {},
    createProgram: () => ({}),
    attachShader: () => {},
    linkProgram: () => {},
    deleteShader: () => {},
    getProgramParameter: () => true,
    useProgram: () => {},
    createBuffer: () => ({}),
    bindBuffer: () => {},
    bufferData: () => {},
    getAttribLocation: () => 0,
    enableVertexAttribArray: () => {},
    vertexAttribPointer: () => {},
    getUniformLocation: (_program: unknown, name: string) => name,
    uniform2f: () => {},
    uniform1f: () => {},
    uniform3f: (_location: unknown, ...rgb: number[]) => calls.uniform3f.push(rgb),
    viewport: () => {},
    drawArrays: () => {
      calls.draws += 1
    },
    deleteBuffer: () => {},
    deleteProgram: () => {},
    getExtension: () => ({ loseContext: () => (calls.lost = true) }),
  }
  return { gl, calls }
}

describe('DottedVeil', () => {
  let fake: ReturnType<typeof fakeGl>

  beforeEach(() => {
    fake = fakeGl()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
      () => fake.gl as unknown as RenderingContext,
    )
  })

  afterEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('is a decorative canvas that draws nothing without WebGL', () => {
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(null)
    const { container } = render(<DottedVeil className="dotted-veil" />)
    const canvas = container.querySelector('canvas')
    expect(canvas).toHaveAttribute('aria-hidden', 'true')
    expect(fake.calls.draws).toBe(0)
  })

  it('draws black dots on white in the light theme and white on black in the dark one', async () => {
    render(<DottedVeil />)
    await vi.waitFor(() => expect(fake.calls.draws).toBeGreaterThan(0))
    // ground, then dot
    expect(fake.calls.uniform3f.slice(0, 2)).toEqual([
      [1, 1, 1],
      [0, 0, 0],
    ])

    document.documentElement.classList.add('dark')
    await vi.waitFor(() =>
      expect(fake.calls.uniform3f.slice(-2)).toEqual([
        [0, 0, 0],
        [1, 1, 1],
      ]),
    )
  })

  it('draws one still frame when motion is reduced', async () => {
    setMediaQueries({ '(prefers-reduced-motion: reduce)': true })
    render(<DottedVeil />)
    await vi.waitFor(() => expect(fake.calls.draws).toBe(1))
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(fake.calls.draws).toBe(1)
  })

  it('keeps drawing while motion is allowed and lets the context go on unmount', async () => {
    const { unmount } = render(<DottedVeil />)
    await vi.waitFor(() => expect(fake.calls.draws).toBeGreaterThan(2))
    unmount()
    expect(fake.calls.lost).toBe(true)
  })
})
