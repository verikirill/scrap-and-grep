import { cancelRender, continueRender, delayRender, staticFile } from 'remotion'
import { DISPLAY_FONT, TEXT_FONT } from './theme'

// Only the Cyrillic and Latin subsets are bundled; the rest of the world's
// scripts do not occur in the digests.
const CYRILLIC = 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116'
const LATIN =
  'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'

const FACES = [
  [DISPLAY_FONT, 'fonts/unbounded-cyrillic-wght-normal.woff2', CYRILLIC],
  [DISPLAY_FONT, 'fonts/unbounded-latin-wght-normal.woff2', LATIN],
  [TEXT_FONT, 'fonts/onest-cyrillic-wght-normal.woff2', CYRILLIC],
  [TEXT_FONT, 'fonts/onest-latin-wght-normal.woff2', LATIN],
] as const

/**
 * Load the bundled fonts before the first frame is captured. Nothing is
 * fetched from the internet: the renderer runs without network access.
 * Characters outside these subsets (₽, for one) fall back to the DejaVu fonts
 * installed in the renderer image.
 */
export function loadFonts(): void {
  const handle = delayRender('Loading fonts')
  // Built inside the promise chain, so that a synchronous error also ends
  // up in cancelRender instead of leaving the render waiting for its timeout.
  Promise.resolve()
    .then(() =>
      Promise.all(
        FACES.map(([family, file, range]) => {
          const face = new FontFace(family, `url('${staticFile(file)}') format('woff2')`, {
            weight: '100 900',
            unicodeRange: range,
          })
          return face.load().then((loaded) => document.fonts.add(loaded))
        }),
      ),
    )
    .then(() => continueRender(handle))
    .catch((error: unknown) => cancelRender(error))
}
