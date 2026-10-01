import { Hct } from 'material-color/hct/hct.js'
import { TonalPalette } from 'material-color/palettes/tonal_palette.js'
import { argbFromHex, hexFromArgb } from 'material-color/utils/string_utils.js'
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

/** Colours from the palette (tag-* roles in styles/palette.css). */
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
 * Tones of the palette colours (scripts/palette.mjs), light theme then dark:
 * the tile, the icon on it and the picker dot. A colour of one's own gets the
 * same tones of its own hue, so it is as legible as the built-in ones.
 */
const TILE = [90, 30] as const
const ICON = [30, 90] as const
const DOT = [55, 70] as const

// A slider passes through many colours; only the last few are worth keeping.
const PALETTES_KEPT = 64
const palettes = new Map<string, TonalPalette>()

function themed(hex: string, [light, dark]: readonly [number, number]): string {
  let palette = palettes.get(hex)
  if (!palette) {
    if (palettes.size >= PALETTES_KEPT) palettes.clear()
    palette = TonalPalette.fromInt(argbFromHex(hex))
    palettes.set(hex, palette)
  }
  // light-dark() follows color-scheme, which the theme switch sets on the root.
  return `light-dark(${hexFromArgb(palette.tone(light))}, ${hexFromArgb(palette.tone(dark))})`
}

/** Hue (0-360) and colourfulness of a colour, as the custom picker shows them. */
export function hueAndChroma(hex: string): { hue: number; chroma: number } {
  const hct = Hct.fromInt(argbFromHex(hex))
  return { hue: Math.round(hct.hue), chroma: Math.round(hct.chroma) }
}

/** The colour of a hue and colourfulness, at the middle tone. */
export function colorOf(hue: number, chroma: number): string {
  return hexFromArgb(Hct.from(hue, chroma, 50).toInt())
}

/** The colour as a picker dot. */
export function swatchColor(key: string): string {
  return isCustomColor(key) ? themed(key, DOT) : `var(--md-swatch-${key})`
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
  return { background: `var(--md-tag-${known})`, color: `var(--md-on-tag-${known})` }
}
