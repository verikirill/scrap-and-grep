// Writes src/components/icons.tsx: the app's icons as Material Symbols Rounded.
//
//   node scripts/icons.mjs
//
// Each name the code imports maps to a Material Symbols icon. The outlined
// form is the default; the filled form shows a chosen or active item, as
// Material 3 does in navigation. A name missing from the set stops the script.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const ICONS = {
  ArrowDown: 'arrow-downward',
  ArrowRight: 'arrow-forward',
  ArrowUp: 'arrow-upward',
  Bold: 'format-bold',
  Bookmark: 'bookmark',
  Bot: 'smart-toy',
  BriefcaseBusiness: 'work',
  CalendarClock: 'calendar-clock',
  Captions: 'closed-caption',
  Check: 'check',
  ChevronDown: 'keyboard-arrow-down',
  ChevronRight: 'chevron-right',
  ChevronLeft: 'chevron-left',
  ChevronUp: 'keyboard-arrow-up',
  CircleAlert: 'error',
  CircleCheck: 'check-circle',
  Clapperboard: 'movie',
  Code: 'code',
  Compass: 'explore',
  Download: 'download',
  ExternalLink: 'open-in-new',
  Eye: 'visibility',
  EyeOff: 'visibility-off',
  FilePen: 'edit-document',
  FileText: 'description',
  Heading2: 'format-h2',
  Heart: 'favorite',
  ImageOff: 'hide-image',
  Info: 'info',
  Italic: 'format-italic',
  KeyRound: 'key',
  Layers: 'layers',
  Link2: 'link',
  List: 'format-list-bulleted',
  ListOrdered: 'format-list-numbered',
  Loader2: 'progress-activity',
  LogIn: 'login',
  LogOut: 'logout',
  Mic: 'mic',
  Minus: 'remove',
  Moon: 'dark-mode',
  OctagonX: 'dangerous',
  PenLine: 'edit',
  Plus: 'add',
  Quote: 'format-quote',
  Radar: 'radar',
  RefreshCw: 'refresh',
  RotateCcw: 'replay',
  RotateCw: 'refresh',
  Rss: 'rss-feed',
  Save: 'save',
  ScanText: 'document-scanner',
  Search: 'search',
  Send: 'send',
  Settings2: 'settings',
  ShieldCheck: 'verified-user',
  SlidersHorizontal: 'tune',
  Sparkles: 'bolt',
  Strikethrough: 'format-strikethrough',
  Sun: 'light-mode',
  Target: 'target',
  ThumbsDown: 'thumb-down',
  ThumbsUp: 'thumb-up',
  Trash2: 'delete',
  TriangleAlert: 'warning',
  Underline: 'format-underlined',
  UserPlus: 'person-add',
  Users: 'group',
  X: 'close',
  Newspaper: 'newspaper',
  DynamicFeed: 'dynamic-feed',
  CompareArrows: 'compare-arrows',
  Schedule: 'schedule',
  ContentCopy: 'content-copy',
  Hub: 'hub',
  CalendarMonth: 'calendar-month',
  Terminal: 'terminal',
  Account: 'account-circle',
  GitCompareArrows: 'compare-arrows',
  Shield: 'shield',
  Factory: 'factory',
  ElectricBolt: 'electric-bolt',
  Dns: 'dns',
  Cloud: 'cloud',
  Memory: 'memory',
  Router: 'router',
  Database: 'database',
  Policy: 'policy',
  Gavel: 'gavel',
  Analytics: 'analytics',
  RocketLaunch: 'rocket-launch',
  BugReport: 'bug-report',
  Lock: 'lock',
  Psychology: 'psychology',
  School: 'school',
  SatelliteAlt: 'satellite-alt',
  Language: 'language',
  Palette: 'palette',
  FileUp: 'upload-file',
  Share: 'share',
  LinkOff: 'link-off',
  Colorize: 'colorize',
  LibraryAdd: 'library-add',
  AutoAwesome: 'auto-awesome',
  TrendingUp: 'trending-up',
  TrendingDown: 'trending-down',
  Block: 'block',
  Camera: 'photo-camera',
  EventRepeat: 'event-repeat',
}

// The names shadcn components import.
const SHADCN_ALIASES = ['Check', 'X', 'ChevronDown', 'ChevronLeft', 'ChevronRight', 'ChevronUp', 'Info', 'TriangleAlert', 'CircleCheck', 'OctagonX', 'Loader2', 'Bot']

const root = new URL('..', import.meta.url)
const set = JSON.parse(readFileSync(new URL('node_modules/@iconify-json/material-symbols/icons.json', root), 'utf8'))
const known = new Set([...Object.keys(set.icons), ...Object.keys(set.aliases ?? {})])
const pick = (...names) => names.find((name) => known.has(name))

const imported = new Map()
const component = (name) => {
  if (!imported.has(name)) {
    imported.set(name, `${name.replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase())}Svg`)
  }
  return imported.get(name)
}

const exported = Object.entries(ICONS).map(([name, base]) => {
  const outline = pick(`${base}-outline-rounded`, `${base}-rounded`, base)
  const filled = pick(`${base}-rounded`, base)
  if (!outline) throw new Error(`Material Symbols has no "${base}" for ${name}`)
  const args = filled && filled !== outline ? `${component(outline)}, ${component(filled)}` : component(outline)
  return `export const ${name} = /* @__PURE__ */ icon(${args})`
})

const source = `// Icons of the app: Material Symbols Rounded, the set Material 3 is drawn with.
// They are compiled into components at build time (unplugin-icons), so only
// the icons used here reach the bundle. Names follow the ones the code used
// with lucide, so a file swaps its import path and nothing else.
// Written by scripts/icons.mjs: edit the list there, not this file.
// Every export is a component made by icon(), which the rule cannot see.
/* oxlint-disable react/only-export-components */
import type { ComponentType, SVGProps } from 'react'
${[...imported].sort(([a], [b]) => a.localeCompare(b)).map(([name, id]) => `import ${id} from '~icons/material-symbols/${name}'`).join('\n')}

type Svg = ComponentType<SVGProps<SVGSVGElement>>

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'fill'> & {
  size?: number | string
  /** Kept for call sites written for stroke icons; these glyphs are filled shapes. */
  strokeWidth?: number | string
  /** The filled form, as Material 3 shows an active or chosen item. */
  filled?: boolean
  /** "currentColor" asks for the filled form, as it did with stroke icons. */
  fill?: string
}

export type IconComponent = ComponentType<IconProps>

function icon(Outline: Svg, Filled: Svg = Outline): IconComponent {
  function Icon({ size = 24, strokeWidth: _stroke, filled, fill, ...props }: IconProps) {
    const Glyph = filled || fill === 'currentColor' ? Filled : Outline
    const isLabelled = props['aria-label'] !== undefined
    return (
      <Glyph
        width={size}
        height={size}
        focusable="false"
        aria-hidden={isLabelled ? undefined : true}
        role={isLabelled ? 'img' : undefined}
        {...props}
      />
    )
  }
  return Icon
}

${exported.join('\n')}

// The names shadcn components import.
${SHADCN_ALIASES.map((name) => `export const ${name}Icon = ${name}`).join('\n')}
`

writeFileSync(fileURLToPath(new URL('src/components/icons.tsx', root)), source)
console.log(`${exported.length} icons, ${imported.size} glyphs`)
