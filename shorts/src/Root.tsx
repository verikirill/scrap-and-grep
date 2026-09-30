import { Composition } from 'remotion'
import type { CalculateMetadataFunction } from 'remotion'
import { DigestShort } from './DigestShort'
import { loadFonts } from './fonts'
import { SAMPLE_PROPS } from './sample'
import { shortSchema } from './schema'
import { FPS, HEIGHT, WIDTH } from './theme'
import type { ShortProps } from './types'

loadFonts()

// A short beat of silence after the last word, so the video does not cut
// the voice off mid-breath.
const TAIL_MS = 700

const metadata: CalculateMetadataFunction<ShortProps> = ({ props }) => ({
  durationInFrames: Math.ceil(((props.durationMs + TAIL_MS) / 1000) * FPS),
})

export function Root() {
  return (
    <Composition
      id="DigestShort"
      component={DigestShort}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={FPS * 30}
      schema={shortSchema}
      defaultProps={SAMPLE_PROPS}
      calculateMetadata={metadata}
    />
  )
}
