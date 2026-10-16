// Writes src/components/icons.tsx: the app's icons from Gravity UI, the set HeroUI is drawn with.
//
//   node scripts/icons.mjs
//
// Each name the code imports maps to a Gravity UI icon. The outlined
// form is the default; the filled form shows a chosen or active item, as
// the navigation does. A name missing from the set stops the script.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const ICONS = {
  ArrowDown: 'arrow-down',
  ArrowRight: 'arrow-right',
  ArrowUp: 'arrow-up',
  Bold: 'bold',
  Bookmark: 'bookmark',
  Bot: 'face-robot',
  BriefcaseBusiness: 'briefcase',
  CalendarClock: 'clock',
  Captions: 'text',
  Check: 'check',
  ChevronDown: 'chevron-down',
  ChevronRight: 'chevron-right',
  ChevronLeft: 'chevron-left',
  ChevronUp: 'chevron-up',
  CircleAlert: 'circle-exclamation',
  CircleCheck: 'circle-check',
  Clapperboard: 'filmstrip',
  Code: 'code',
  Compass: 'compass',
  Download: 'arrow-down-to-line',
  ExternalLink: 'arrow-up-right-from-square',
  Eye: 'eye',
  EyeOff: 'eye-slash',
  FilePen: 'pencil-to-square',
  FileText: 'file-text',
  Heading2: 'heading-2',
  Heart: 'heart',
  Play: 'play',
  Square: 'stop',
  ImageOff: 'picture',
  Info: 'circle-info',
  Italic: 'italic',
  KeyRound: 'key',
  Layers: 'layers',
  Link2: 'link',
  List: 'list-ul',
  ListOrdered: 'list-ol',
  Loader2: 'arrows-rotate-right',
  LogIn: 'arrow-right-to-square',
  LogOut: 'arrow-right-from-square',
  Mic: 'microphone',
  Minus: 'minus',
  Moon: 'moon',
  OctagonX: 'octagon-xmark',
  PenLine: 'pencil',
  Plus: 'plus',
  Quote: 'quote-open',
  Radar: 'target-dart',
  RefreshCw: 'arrows-rotate-right',
  RotateCcw: 'arrow-rotate-left',
  RotateCw: 'arrow-rotate-right',
  Rss: 'broadcast-signal',
  Save: 'floppy-disk',
  ScanText: 'file-magnifier',
  Search: 'magnifier',
  Send: 'paper-plane',
  Settings2: 'gear',
  ShieldCheck: 'shield-check',
  SlidersHorizontal: 'sliders',
  Sparkles: 'sparkles',
  Strikethrough: 'strikethrough',
  Sun: 'sun',
  Target: 'target',
  ThumbsDown: 'thumbs-down',
  ThumbsUp: 'thumbs-up',
  Trash2: 'trash-bin',
  TriangleAlert: 'triangle-exclamation',
  Underline: 'underline',
  UserPlus: 'person-plus',
  Users: 'persons',
  X: 'xmark',
  Newspaper: 'square-article',
  DynamicFeed: 'layout-list',
  CompareArrows: 'arrow-right-arrow-left',
  Schedule: 'clock',
  ContentCopy: 'copy',
  Hub: 'nodes-down',
  CalendarMonth: 'calendar',
  ViewCards: 'layout-rows',
  ViewChat: 'comment',
  Terminal: 'terminal',
  Account: 'person',
  GitCompareArrows: 'code-compare',
  Shield: 'shield',
  Factory: 'factory',
  ElectricBolt: 'thunderbolt',
  Dns: 'server',
  Cloud: 'cloud',
  Memory: 'cpu',
  Router: 'antenna-signal',
  Database: 'database',
  Policy: 'shield-keyhole',
  Gavel: 'scales-balanced',
  Analytics: 'chart-column',
  RocketLaunch: 'rocket',
  BugReport: 'bug',
  Lock: 'lock',
  Psychology: 'bulb',
  School: 'graduation-cap',
  SatelliteAlt: 'signal',
  Language: 'globe',
  Palette: 'palette',
  FileUp: 'file-arrow-up',
  Share: 'arrow-shape-turn-up-right',
  LinkOff: 'link-slash',
  Colorize: 'droplet',
  LibraryAdd: 'square-plus',
  AutoAwesome: 'magic-wand',
  TrendingUp: 'chart-line-arrow-up',
  TrendingDown: 'arrow-down-right',
  Block: 'ban',
  Camera: 'camera',
  EventRepeat: 'arrows-rotate-left',
  Help: 'circle-question',
}

// The names shadcn components import.
const SHADCN_ALIASES = ['Check', 'X', 'ChevronDown', 'ChevronLeft', 'ChevronRight', 'ChevronUp', 'Info', 'TriangleAlert', 'CircleCheck', 'OctagonX', 'Loader2', 'Bot']

const root = new URL('..', import.meta.url)
const set = JSON.parse(readFileSync(new URL('node_modules/@iconify-json/gravity-ui/icons.json', root), 'utf8'))
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
  const outline = pick(base)
  const filled = pick(`${base}-fill`, base)
  if (!outline) throw new Error(`Gravity UI has no "${base}" for ${name}`)
  const args = filled && filled !== outline ? `${component(outline)}, ${component(filled)}` : component(outline)
  return `export const ${name} = /* @__PURE__ */ icon(${args})`
})

const source = `// Icons of the app: Gravity UI, the set HeroUI is drawn with.
// They are compiled into components at build time (unplugin-icons), so only
// the icons used here reach the bundle. Names follow the ones the code used
// with lucide, so a file swaps its import path and nothing else.
// Written by scripts/icons.mjs: edit the list there, not this file.
// Every export is a component made by icon(), which the rule cannot see.
/* oxlint-disable react/only-export-components */
import type { ComponentType, SVGProps } from 'react'
${[...imported].sort(([a], [b]) => a.localeCompare(b)).map(([name, id]) => `import ${id} from '~icons/gravity-ui/${name}'`).join('\n')}

type Svg = ComponentType<SVGProps<SVGSVGElement>>

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'fill'> & {
  size?: number | string
  /** Kept for call sites written for stroke icons; these glyphs are filled shapes. */
  strokeWidth?: number | string
  /** The filled form, for an active or chosen item. */
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
