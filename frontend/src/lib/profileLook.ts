import { hexToOklch, oklchToHex } from './oklch'
import {
  Analytics,
  BriefcaseBusiness,
  BugReport,
  Cloud,
  Code,
  Database,
  Dns,
  ElectricBolt,
  Factory,
  Gavel,
  Hub,
  Language,
  Lock,
  Memory,
  Policy,
  Psychology,
  RocketLaunch,
  Router,
  SatelliteAlt,
  School,
  Shield,
} from '../components/icons'
import type { IconComponent } from '../components/icons'

/**
 * Icons a reader can give a profile. The keys are stored with the profile;
 * a key this list does not know draws the default.
 */
export const PROFILE_ICONS: { key: string; label: string; icon: IconComponent }[] = [
  { key: 'shield', label: 'Защита', icon: Shield },
  { key: 'factory', label: 'Производство', icon: Factory },
  { key: 'energy', label: 'Энергетика', icon: ElectricBolt },
  { key: 'servers', label: 'Серверы', icon: Dns },
  { key: 'network', label: 'Сеть', icon: Hub },
  { key: 'router', label: 'Оборудование', icon: Router },
  { key: 'cloud', label: 'Облако', icon: Cloud },
  { key: 'chip', label: 'Электроника', icon: Memory },
  { key: 'database', label: 'Данные', icon: Database },
  { key: 'code', label: 'Разработка', icon: Code },
  { key: 'bug', label: 'Уязвимости', icon: BugReport },
  { key: 'lock', label: 'Доступ', icon: Lock },
  { key: 'policy', label: 'Требования', icon: Policy },
  { key: 'law', label: 'Регуляторы', icon: Gavel },
  { key: 'analytics', label: 'Аналитика', icon: Analytics },
  { key: 'ai', label: 'ИИ', icon: Psychology },
  { key: 'rocket', label: 'Запуски', icon: RocketLaunch },
  { key: 'satellite', label: 'Связь', icon: SatelliteAlt },
  { key: 'web', label: 'Веб', icon: Language },
  { key: 'study', label: 'Обучение', icon: School },
  { key: 'work', label: 'Работа', icon: BriefcaseBusiness },
]

/** Tag colours (styles/tags.css). */
export const PROFILE_COLORS = [
  { key: 'blue', label: 'Синий' },
  { key: 'violet', label: 'Фиолетовый' },
  { key: 'teal', label: 'Бирюзовый' },
  { key: 'green', label: 'Зелёный' },
  { key: 'amber', label: 'Янтарный' },
  { key: 'orange', label: 'Оранжевый' },
  { key: 'red', label: 'Красный' },
  { key: 'pink', label: 'Розовый' },
  { key: 'slate', label: 'Графитовый' },
] as const

export const DEFAULT_COLOR = 'blue'

export function profileIcon(key: string | null | undefined): IconComponent | null {
  return PROFILE_ICONS.find((item) => item.key === key)?.icon ?? null
}

const HEX = /^#[0-9a-f]{6}$/

/** A colour of the reader's own: #rrggbb in lower case. */
export type HexColor = `#${string}`

/** A colour of the reader's own, stored as #rrggbb instead of a palette key. */
export function isCustomColor(value: string | null | undefined): value is HexColor {
  return typeof value === 'string' && HEX.test(value)
}

/*
 * Tones of a colour of one's own, light theme then dark, at fixed OKLCH
 * lightness: the tile, the icon on it and the picker dot. The chroma keeps the
 * colour's own up to a cap per tone, so a loud colour still gives a calm tile.
 */
type Tone = { l: number; maxC: number }
const TILE: readonly [Tone, Tone] = [
  { l: 0.93, maxC: 0.06 },
  { l: 0.33, maxC: 0.09 },
]
const ICON: readonly [Tone, Tone] = [
  { l: 0.42, maxC: 0.16 },
  { l: 0.9, maxC: 0.07 },
]
const DOT: readonly [Tone, Tone] = [
  { l: 0.62, maxC: 0.2 },
  { l: 0.74, maxC: 0.16 },
]

/** The picker's colourfulness scale: 0-80 across the chroma a screen shows well. */
const CHROMA_SCALE = 400

function tone(hex: string, { l, maxC }: Tone): string {
  const { c, h } = hexToOklch(hex)
  return oklchToHex({ l, c: Math.min(c, maxC), h })
}

function themed(hex: string, [light, dark]: readonly [Tone, Tone]): string {
  // light-dark() follows color-scheme, which the theme switch sets on the root.
  return `light-dark(${tone(hex, light)}, ${tone(hex, dark)})`
}

/** Hue (0-360) and colourfulness (0-80) of a colour, as the custom picker shows them. */
export function hueAndChroma(hex: string): { hue: number; chroma: number } {
  const { c, h } = hexToOklch(hex)
  return { hue: Math.round(h) % 360, chroma: Math.round(c * CHROMA_SCALE) }
}

/** The colour of a hue and colourfulness, at the middle tone. */
export function colorOf(hue: number, chroma: number): string {
  return oklchToHex({ l: 0.62, c: chroma / CHROMA_SCALE, h: hue })
}

/** The colour as a picker dot. */
export function swatchColor(key: string): string {
  return isCustomColor(key) ? themed(key, DOT) : `var(--swatch-${key})`
}

/**
 * The tile and icon colours of a profile, as CSS. An unknown value is the
 * default colour: nothing but a palette key or a hex code reaches a style.
 */
export function profileColors(key: string | null | undefined): {
  background: string
  color: string
} {
  if (isCustomColor(key)) return { background: themed(key, TILE), color: themed(key, ICON) }
  const known = PROFILE_COLORS.some((item) => item.key === key) ? key : DEFAULT_COLOR
  return { background: `var(--tag-${known})`, color: `var(--on-tag-${known})` }
}
