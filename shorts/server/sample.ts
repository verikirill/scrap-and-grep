// Render the sample props to out/sample.mp4: a quick check that fonts,
// scenes and captions come out right, without the backend.
//
//   node server/sample.ts
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { SAMPLE_PROPS } from '../src/sample.ts'
import { renderShort } from './render.ts'

const out = path.resolve(import.meta.dirname, '..', 'out')
mkdirSync(out, { recursive: true })
const started = performance.now()
let shown = -1
const result = await renderShort({
  props: SAMPLE_PROPS,
  output: path.join(out, 'sample.mp4'),
  onProgress: (share) => {
    const percent = Math.floor(share * 10) * 10
    if (percent !== shown) {
      shown = percent
      process.stdout.write(`${percent}% `)
    }
  },
})
const seconds = (performance.now() - started) / 1000
console.log(`\n${result.frames} frames at ${result.fps} fps in ${seconds.toFixed(1)} s`)
