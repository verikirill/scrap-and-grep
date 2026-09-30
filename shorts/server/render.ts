import { existsSync } from 'node:fs'
import path from 'node:path'
import { bundle } from '@remotion/bundler'
import { renderMedia, selectComposition } from '@remotion/renderer'
import type { CancelSignal } from '@remotion/renderer'
import type { ShortProps } from '../src/types.ts'

const ROOT = path.resolve(import.meta.dirname, '..')
// Bundled once at image build time (see Dockerfile); bundling on the fly is
// the fallback for local runs.
const PREBUILT = path.join(ROOT, 'build')

let serveUrl: Promise<string> | null = null

export function bundled(): Promise<string> {
  serveUrl ??= existsSync(path.join(PREBUILT, 'index.html'))
    ? Promise.resolve(PREBUILT)
    : bundle({ entryPoint: path.join(ROOT, 'src', 'index.ts') })
  return serveUrl
}

export async function prebundle(): Promise<string> {
  return bundle({ entryPoint: path.join(ROOT, 'src', 'index.ts'), outDir: PREBUILT })
}

type RenderOptions = {
  props: ShortProps
  /** Where to write the MP4; without it the video comes back as a buffer. */
  output?: string
  concurrency?: number | null
  cancelSignal?: CancelSignal
  onProgress?: (share: number) => void
}

export type RenderResult = { frames: number; fps: number; video: Buffer | null }

/** Render one short to an MP4 file or buffer. */
export async function renderShort({
  props,
  output,
  concurrency,
  cancelSignal,
  onProgress,
}: RenderOptions): Promise<RenderResult> {
  // selectComposition takes no cancel signal and starts a browser, so a
  // request cancelled before or during it stops here instead.
  let isCancelled = false
  cancelSignal?.(() => {
    isCancelled = true
  })
  const url = await bundled()
  const composition = await selectComposition({ serveUrl: url, id: 'DigestShort', inputProps: props })
  if (isCancelled) {
    throw new Error('the render was cancelled')
  }
  const { buffer } = await renderMedia({
    codec: 'h264',
    composition,
    serveUrl: url,
    outputLocation: output ?? null,
    inputProps: props,
    concurrency: concurrency ?? null,
    // Shorts are watched on phones; a 60 s video came out at 14 MB.
    crf: 23,
    chromiumOptions: { enableMultiProcessOnLinux: true },
    cancelSignal,
    onProgress: ({ progress }) => onProgress?.(progress),
  })
  return { frames: composition.durationInFrames, fps: composition.fps, video: buffer }
}
