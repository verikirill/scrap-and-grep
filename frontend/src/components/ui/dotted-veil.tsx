// A barely visible halftone of slowly breathing dots behind the app, after the
// "Halftone" preset of the 21st.dev Shader Builder. One WebGL canvas, no
// dependencies. It is monochrome: white dots on black, laid over the page with
// `screen` in the dark theme, black dots on white with `multiply` in the light
// one, so only the dots show whatever the surface colour is (see .dotted-veil
// in index.css). Without WebGL it draws nothing; with reduced motion it draws
// one still frame.

import { useEffect, useRef } from 'react'

const VERT = `attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}`

// The shader keeps only what the halftone uses: a dot grid whose dot size
// follows a slow wave, two colours and a little grain.
const FRAG = `#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform vec3 u_ground;
uniform vec3 u_dot;

float grainHash(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

void main() {
  vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
  p *= 1.1;
  float cells = 26.7;
  vec2 f = fract(p * cells) - 0.5;
  float field = 0.5 + 0.5 * sin(p.x * 3.0 + u_time + 2.3) * sin(p.y * 2.4 - u_time * 0.7);
  float r = 0.23 + field * 0.2;
  float dotMask = 1.0 - smoothstep(r - 0.08, r, length(f));
  vec3 col = mix(u_ground, u_dot, dotMask * (0.35 + 0.65 * field));
  col += (grainHash(gl_FragCoord.xy) - 0.5) * 0.04;
  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`

// Time runs slowly: the dots breathe, they do not crawl.
const TIME_SCALE = 0.35

function isDark(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function DottedVeil({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const gl = canvas.getContext('webgl', { antialias: false })
    if (!gl) return

    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type)
      if (!shader) return null
      gl.shaderSource(shader, source)
      gl.compileShader(shader)
      return shader
    }
    const program = gl.createProgram()
    const vertex = compile(gl.VERTEX_SHADER, VERT)
    const fragment = compile(gl.FRAGMENT_SHADER, FRAG)
    if (!program || !vertex || !fragment) return
    gl.attachShader(program, vertex)
    gl.attachShader(program, fragment)
    gl.linkProgram(program)
    gl.deleteShader(vertex)
    gl.deleteShader(fragment)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return
    gl.useProgram(program)

    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const position = gl.getAttribLocation(program, 'a_position')
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)

    const resolution = gl.getUniformLocation(program, 'u_resolution')
    const time = gl.getUniformLocation(program, 'u_time')
    const ground = gl.getUniformLocation(program, 'u_ground')
    const dot = gl.getUniformLocation(program, 'u_dot')

    const paint = () => {
      // Screen in the dark theme lets white dots through and black vanish;
      // multiply in the light one does the same for black dots on white.
      if (isDark()) {
        gl.uniform3f(ground, 0, 0, 0)
        gl.uniform3f(dot, 1, 1, 1)
      } else {
        gl.uniform3f(ground, 1, 1, 1)
        gl.uniform3f(dot, 0, 0, 0)
      }
    }
    paint()

    const still = matchMedia('(prefers-reduced-motion: reduce)').matches
    const start = performance.now()
    let raf = 0
    let visible = document.visibilityState === 'visible'

    const resize = () => {
      const scale = Math.min(window.devicePixelRatio || 1, 1.5)
      const width = Math.max(1, Math.round(canvas.clientWidth * scale))
      const height = Math.max(1, Math.round(canvas.clientHeight * scale))
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width
        canvas.height = height
        gl.viewport(0, 0, width, height)
      }
    }

    const draw = (now: number) => {
      raf = 0
      resize()
      gl.uniform2f(resolution, canvas.width, canvas.height)
      gl.uniform1f(time, still ? 0 : ((now - start) / 1000) * TIME_SCALE)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
      if (!still && visible) raf = requestAnimationFrame(draw)
    }
    const redraw = () => {
      if (raf === 0) raf = requestAnimationFrame(draw)
    }

    const onVisibility = () => {
      visible = document.visibilityState === 'visible'
      if (visible) redraw()
      else if (raf !== 0) {
        cancelAnimationFrame(raf)
        raf = 0
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('resize', redraw)
    // The theme is a class on <html>: follow it without a re-render.
    const themeWatch = new MutationObserver(() => {
      paint()
      redraw()
    })
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    redraw()

    return () => {
      cancelAnimationFrame(raf)
      themeWatch.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('resize', redraw)
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
      gl.getExtension('WEBGL_lose_context')?.loseContext()
    }
  }, [])

  return <canvas ref={canvasRef} aria-hidden="true" className={className} />
}
