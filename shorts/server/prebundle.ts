// Bundle the compositions into build/ once, at image build time, so the
// service starts rendering without a webpack run.
//
//   node server/prebundle.ts
import { prebundle } from './render.ts'

const out = await prebundle()
process.stdout.write(`bundled to ${out}\n`)
