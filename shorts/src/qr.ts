import { create } from 'qrcode'

// Whole pixels a module keep every module the same size in the encoded
// video. Below four a camera no longer reads the code off a phone screen
// (DECISIONS.md), so a denser code is left out rather than shrunk.
export const MIN_MODULE_PX = 4
const MAX_MODULE_PX = 8
export const MAX_QR_SIZE = 250
// The standard asks for a light margin four modules wide around the code.
const QUIET_MODULES = 4

export type QrLayout = { px: number; size: number; padding: number }
export type Qr = QrLayout & { path: string; modules: number }

/** How big to draw a code of this many modules a side, or null if it cannot be read. */
export function qrLayout(modules: number): QrLayout | null {
  const px = Math.min(MAX_MODULE_PX, Math.floor(MAX_QR_SIZE / modules))
  if (px < MIN_MODULE_PX) return null
  return { px, size: px * modules, padding: px * QUIET_MODULES }
}

/** The QR code of a text as one SVG path, or null if it would not scan. */
export function makeQr(value: string): Qr | null {
  let matrix: ReturnType<typeof create>['modules']
  try {
    matrix = create(value, { errorCorrectionLevel: 'M' }).modules
  } catch {
    // More than a QR code holds: the card goes without one.
    return null
  }
  const layout = qrLayout(matrix.size)
  if (!layout) return null
  const squares: string[] = []
  for (let row = 0; row < matrix.size; row += 1) {
    for (let col = 0; col < matrix.size; col += 1) {
      if (matrix.get(row, col)) {
        squares.push(`M${col} ${row}h1v1h-1z`)
      }
    }
  }
  return { ...layout, path: squares.join(''), modules: matrix.size }
}
