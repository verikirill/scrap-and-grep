import { useMemo } from 'react'
import { makeQr } from '../qr'
import type { Qr } from '../qr'

/** The QR code of a text, computed once per text. */
export function useQr(value: string | null): Qr | null {
  return useMemo(() => (value ? makeQr(value) : null), [value])
}

/**
 * A QR code drawn from its matrix, one square per dark module. No markup from
 * outside ever reaches the page, and every frame renders the same.
 */
export function QrCode({ qr, color }: { qr: Qr; color: string }) {
  return (
    <svg
      viewBox={`0 0 ${qr.modules} ${qr.modules}`}
      width={qr.size}
      height={qr.size}
      shapeRendering="crispEdges"
      role="img"
      aria-label="QR-код ссылки на источник"
      style={{ display: 'block' }}
    >
      <path d={qr.path} fill={color} />
    </svg>
  )
}
