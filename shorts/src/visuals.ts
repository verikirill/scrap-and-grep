import {
  ChartColumnIncreasing,
  Crosshair,
  Landmark,
  Newspaper,
  Rocket,
  ShieldAlert,
  Siren,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { VISUALS } from './schema'
import { COLORS } from './theme.ts'

export type Visual = (typeof VISUALS)[number]

/** The picture and the colour of a news card, by what the news is about. */
export const VISUAL_STYLE: Record<Visual, { icon: LucideIcon; color: string }> = {
  vulnerability: { icon: ShieldAlert, color: '#ff5c7a' },
  attack: { icon: Crosshair, color: '#ff7a45' },
  incident: { icon: Siren, color: '#ffb020' },
  regulation: { icon: Landmark, color: COLORS.accent },
  release: { icon: Rocket, color: '#3ddc97' },
  research: { icon: ChartColumnIncreasing, color: '#4cc9f0' },
  energy: { icon: Zap, color: COLORS.spark },
  other: { icon: Newspaper, color: '#9aa7c7' },
}

/** What a fact looks like as a picture: a CVSS gauge, a share, a number, an identifier. */
export type FactShape =
  | { kind: 'cvss'; score: number }
  | { kind: 'percent'; value: number; label: string }
  | { kind: 'number'; value: number; decimals: number; suffix: string }
  | { kind: 'text'; text: string }

const CVSS_RE = /^CVSS\s+(\d{1,2}(?:[.,]\d)?)$/i
const PERCENT_RE = /^(\d{1,3}(?:[.,]\d+)?)\s?%$/
// A count and what it counts, apart: "48 часов", "1,5 млрд рублей",
// "12 000 записей" (\s takes the no-break spaces of grouped digits too).
// "0-day", "5G", "10:30", "7.6.3", "30.09.2026" and "3 000" with nothing
// counted do not match and stay text.
const NUMBER_RE = /^(\d{1,3}(?:\s\d{3})+|\d+)(?:[.,](\d+))?\s+([^\d\s].*)$/
// A year or a date counting up from zero reads as nonsense; it stays text.
const YEAR_RE = /^(19|20)\d\d$/
const MONTH_RE = /^(январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)/i
const GROUP_SPACE_RE = /\s/g
// Millions and billions are counted in their own words, as the press does.
const SCALES = [
  [1e9, 'млрд'],
  [1e6, 'млн'],
] as const
// Past this a number loses digits in a double; it is shown as written.
const MAX_COUNT = 1e15
// Numbers from ten thousand up are grouped by thousands, as in Russian print.
const GROUPING_FROM = 10_000
const NARROW_NBSP = String.fromCharCode(0x202f)
// Width of a digit of Unbounded ExtraBold, in em, with a margin.
const DIGIT_EM = 0.7

const toNumber = (text: string) => Number(text.replace(GROUP_SPACE_RE, '').replace(',', '.'))

/** Up to two decimals, as few as the value needs. */
function shortDecimals(value: number): { value: number; decimals: number } {
  const rounded = Math.round(value * 100) / 100
  if (Number.isInteger(rounded)) return { value: rounded, decimals: 0 }
  return { value: rounded, decimals: Number.isInteger(rounded * 10) ? 1 : 2 }
}

function countShape(whole: string, fraction: string | undefined, suffix: string): FactShape | null {
  if (fraction === undefined && YEAR_RE.test(whole)) return null
  if (MONTH_RE.test(suffix)) return null
  const value = toNumber(fraction === undefined ? whole : `${whole}.${fraction}`)
  if (!Number.isFinite(value) || value >= MAX_COUNT) return null
  const scale = SCALES.find(([from]) => value >= from)
  if (scale) {
    const [from, word] = scale
    return { kind: 'number', ...shortDecimals(value / from), suffix: `${word} ${suffix}` }
  }
  return { kind: 'number', value, decimals: fraction?.length ?? 0, suffix }
}

export function factShape(fact: string): FactShape {
  const cvss = CVSS_RE.exec(fact)
  if (cvss && toNumber(cvss[1]) <= 10) {
    return { kind: 'cvss', score: toNumber(cvss[1]) }
  }
  const percent = PERCENT_RE.exec(fact)
  if (percent && toNumber(percent[1]) <= 100) {
    return { kind: 'percent', value: toNumber(percent[1]), label: fact }
  }
  const number = NUMBER_RE.exec(fact)
  const count = number ? countShape(number[1], number[2], number[3]) : null
  return count ?? { kind: 'text', text: fact }
}

/** A count as it is printed in Russian: decimal comma, thousands apart. */
export function formatCount(value: number, decimals: number): string {
  const [whole, fraction] = value.toFixed(decimals).split('.')
  // Grouped by the digits shown, not by the value before rounding.
  const grouped =
    Math.abs(Number(whole)) >= GROUPING_FROM ? whole.replace(/\B(?=(\d{3})+$)/g, NARROW_NBSP) : whole
  return fraction === undefined ? grouped : `${grouped},${fraction}`
}

/** The largest font size, up to `max`, at which the text fits `width` pixels. */
export function fitFontSize(text: string, width: number, max: number): number {
  return Math.min(max, Math.floor(width / (DIGIT_EM * Math.max(1, text.length))))
}

// Width of an Unbounded capital or digit with its letter spacing, in ems.
const CAPITAL_EM = 0.92
const MIN_LABEL_SIZE = 20

/**
 * Font size that keeps a short label, such as "CVE-2026-71379", on one line
 * of the given width; a label too long for that wraps at the smallest size.
 */
export function labelFontSize(text: string, width: number, max: number): number {
  const fitting = Math.floor(width / (CAPITAL_EM * Math.max(1, text.length)))
  return Math.min(max, Math.max(MIN_LABEL_SIZE, fitting))
}

/** Colour of a CVSS score by the standard's own bands. */
export function severityColor(score: number): string {
  if (score >= 9) return '#ff4d6d'
  if (score >= 7) return '#ff8a3d'
  if (score >= 4) return '#ffd23f'
  return '#3ddc97'
}
