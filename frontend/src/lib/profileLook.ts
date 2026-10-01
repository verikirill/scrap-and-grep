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

/** The colour as a picker dot. */
export function swatchColor(key: string): string {
  return `var(--md-swatch-${key})`
}

/** The tile and icon colours of a profile, as CSS: an unknown colour is the default one. */
export function profileColors(key: string | null | undefined): {
  background: string
  color: string
} {
  const known = PROFILE_COLORS.some((item) => item.key === key) ? key : DEFAULT_COLOR
  return { background: `var(--md-tag-${known})`, color: `var(--md-on-tag-${known})` }
}
