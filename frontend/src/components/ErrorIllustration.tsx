import type { ErrorArt } from '../lib/failure'
import { ArtTile } from './ArtTile'

/** The drawings in public/brand/errors/, by the status they stand for, at their own size. */
const ART: Record<ErrorArt, { width: number; height: number }> = {
  404: { width: 668, height: 671 },
  429: { width: 698, height: 720 },
  500: { width: 720, height: 630 },
  503: { width: 720, height: 607 },
}

/**
 * The cat drawn for a page-wide failure: looking for a page that is not
 * there (404), juggling too many requests (429), by a pulled plug (500),
 * asleep while the service is down (503). Decorative: the heading says it.
 * It floats gently, and holds still under "reduce motion" (index.css).
 */
export function ErrorIllustration({
  status,
  size = 240,
  isEager = false,
}: {
  status: ErrorArt
  /** Width in pixels; the height follows the drawing. */
  size?: number
  /** Load at once: the drawing is the first thing on its page. */
  isEager?: boolean
}) {
  const { width, height } = ART[status]
  return (
    <ArtTile>
      <img
        src={`/brand/errors/${status}.webp`}
        alt=""
        aria-hidden
        width={size}
        height={Math.round((size * height) / width)}
        loading={isEager ? 'eager' : 'lazy'}
        decoding="async"
        draggable={false}
        className="error-illustration h-auto max-w-full select-none"
      />
    </ArtTile>
  )
}
