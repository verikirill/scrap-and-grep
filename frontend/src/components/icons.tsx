// Icons of the app: Gravity UI, the set HeroUI is drawn with.
// They are compiled into components at build time (unplugin-icons), so only
// the icons used here reach the bundle. Names follow the ones the code used
// with lucide, so a file swaps its import path and nothing else.
// Written by scripts/icons.mjs: edit the list there, not this file.
// Every export is a component made by icon(), which the rule cannot see.
/* oxlint-disable react/only-export-components */
import type { ComponentType, SVGProps } from 'react'
import AntennaSignalSvg from '~icons/gravity-ui/antenna-signal'
import ArrowDownSvg from '~icons/gravity-ui/arrow-down'
import ArrowDownRightSvg from '~icons/gravity-ui/arrow-down-right'
import ArrowDownToLineSvg from '~icons/gravity-ui/arrow-down-to-line'
import ArrowRightSvg from '~icons/gravity-ui/arrow-right'
import ArrowRightArrowLeftSvg from '~icons/gravity-ui/arrow-right-arrow-left'
import ArrowRightFromSquareSvg from '~icons/gravity-ui/arrow-right-from-square'
import ArrowRightToSquareSvg from '~icons/gravity-ui/arrow-right-to-square'
import ArrowRotateLeftSvg from '~icons/gravity-ui/arrow-rotate-left'
import ArrowRotateRightSvg from '~icons/gravity-ui/arrow-rotate-right'
import ArrowShapeTurnUpRightSvg from '~icons/gravity-ui/arrow-shape-turn-up-right'
import ArrowUpSvg from '~icons/gravity-ui/arrow-up'
import ArrowUpRightFromSquareSvg from '~icons/gravity-ui/arrow-up-right-from-square'
import ArrowsRotateLeftSvg from '~icons/gravity-ui/arrows-rotate-left'
import ArrowsRotateRightSvg from '~icons/gravity-ui/arrows-rotate-right'
import BanSvg from '~icons/gravity-ui/ban'
import BoldSvg from '~icons/gravity-ui/bold'
import BookmarkSvg from '~icons/gravity-ui/bookmark'
import BookmarkFillSvg from '~icons/gravity-ui/bookmark-fill'
import BriefcaseSvg from '~icons/gravity-ui/briefcase'
import BriefcaseFillSvg from '~icons/gravity-ui/briefcase-fill'
import BroadcastSignalSvg from '~icons/gravity-ui/broadcast-signal'
import BugSvg from '~icons/gravity-ui/bug'
import BulbSvg from '~icons/gravity-ui/bulb'
import CalendarSvg from '~icons/gravity-ui/calendar'
import CameraSvg from '~icons/gravity-ui/camera'
import ChartColumnSvg from '~icons/gravity-ui/chart-column'
import ChartLineArrowUpSvg from '~icons/gravity-ui/chart-line-arrow-up'
import CheckSvg from '~icons/gravity-ui/check'
import ChevronDownSvg from '~icons/gravity-ui/chevron-down'
import ChevronLeftSvg from '~icons/gravity-ui/chevron-left'
import ChevronRightSvg from '~icons/gravity-ui/chevron-right'
import ChevronUpSvg from '~icons/gravity-ui/chevron-up'
import CircleCheckSvg from '~icons/gravity-ui/circle-check'
import CircleCheckFillSvg from '~icons/gravity-ui/circle-check-fill'
import CircleExclamationSvg from '~icons/gravity-ui/circle-exclamation'
import CircleExclamationFillSvg from '~icons/gravity-ui/circle-exclamation-fill'
import CircleInfoSvg from '~icons/gravity-ui/circle-info'
import CircleInfoFillSvg from '~icons/gravity-ui/circle-info-fill'
import CircleQuestionSvg from '~icons/gravity-ui/circle-question'
import CircleQuestionFillSvg from '~icons/gravity-ui/circle-question-fill'
import ClockSvg from '~icons/gravity-ui/clock'
import ClockFillSvg from '~icons/gravity-ui/clock-fill'
import CloudSvg from '~icons/gravity-ui/cloud'
import CodeSvg from '~icons/gravity-ui/code'
import CodeCompareSvg from '~icons/gravity-ui/code-compare'
import CompassSvg from '~icons/gravity-ui/compass'
import CopySvg from '~icons/gravity-ui/copy'
import CpuSvg from '~icons/gravity-ui/cpu'
import DatabaseSvg from '~icons/gravity-ui/database'
import DatabaseFillSvg from '~icons/gravity-ui/database-fill'
import DropletSvg from '~icons/gravity-ui/droplet'
import EyeSvg from '~icons/gravity-ui/eye'
import EyeSlashSvg from '~icons/gravity-ui/eye-slash'
import FaceRobotSvg from '~icons/gravity-ui/face-robot'
import FactorySvg from '~icons/gravity-ui/factory'
import FileArrowUpSvg from '~icons/gravity-ui/file-arrow-up'
import FileMagnifierSvg from '~icons/gravity-ui/file-magnifier'
import FileTextSvg from '~icons/gravity-ui/file-text'
import FilmstripSvg from '~icons/gravity-ui/filmstrip'
import FloppyDiskSvg from '~icons/gravity-ui/floppy-disk'
import GearSvg from '~icons/gravity-ui/gear'
import GlobeSvg from '~icons/gravity-ui/globe'
import GraduationCapSvg from '~icons/gravity-ui/graduation-cap'
import Heading2Svg from '~icons/gravity-ui/heading-2'
import HeartSvg from '~icons/gravity-ui/heart'
import HeartFillSvg from '~icons/gravity-ui/heart-fill'
import ItalicSvg from '~icons/gravity-ui/italic'
import KeySvg from '~icons/gravity-ui/key'
import LayersSvg from '~icons/gravity-ui/layers'
import LayoutListSvg from '~icons/gravity-ui/layout-list'
import LinkSvg from '~icons/gravity-ui/link'
import LinkSlashSvg from '~icons/gravity-ui/link-slash'
import ListOlSvg from '~icons/gravity-ui/list-ol'
import ListUlSvg from '~icons/gravity-ui/list-ul'
import LockSvg from '~icons/gravity-ui/lock'
import LockFillSvg from '~icons/gravity-ui/lock-fill'
import MagicWandSvg from '~icons/gravity-ui/magic-wand'
import MagnifierSvg from '~icons/gravity-ui/magnifier'
import MicrophoneSvg from '~icons/gravity-ui/microphone'
import MinusSvg from '~icons/gravity-ui/minus'
import MoonSvg from '~icons/gravity-ui/moon'
import NodesDownSvg from '~icons/gravity-ui/nodes-down'
import OctagonXmarkSvg from '~icons/gravity-ui/octagon-xmark'
import PaletteSvg from '~icons/gravity-ui/palette'
import PaperPlaneSvg from '~icons/gravity-ui/paper-plane'
import PencilSvg from '~icons/gravity-ui/pencil'
import PencilToSquareSvg from '~icons/gravity-ui/pencil-to-square'
import PersonSvg from '~icons/gravity-ui/person'
import PersonFillSvg from '~icons/gravity-ui/person-fill'
import PersonPlusSvg from '~icons/gravity-ui/person-plus'
import PersonsSvg from '~icons/gravity-ui/persons'
import PictureSvg from '~icons/gravity-ui/picture'
import PlusSvg from '~icons/gravity-ui/plus'
import QuoteOpenSvg from '~icons/gravity-ui/quote-open'
import RocketSvg from '~icons/gravity-ui/rocket'
import ScalesBalancedSvg from '~icons/gravity-ui/scales-balanced'
import ServerSvg from '~icons/gravity-ui/server'
import ShieldSvg from '~icons/gravity-ui/shield'
import ShieldCheckSvg from '~icons/gravity-ui/shield-check'
import ShieldKeyholeSvg from '~icons/gravity-ui/shield-keyhole'
import SignalSvg from '~icons/gravity-ui/signal'
import SlidersSvg from '~icons/gravity-ui/sliders'
import SparklesSvg from '~icons/gravity-ui/sparkles'
import SparklesFillSvg from '~icons/gravity-ui/sparkles-fill'
import SquareArticleSvg from '~icons/gravity-ui/square-article'
import SquarePlusSvg from '~icons/gravity-ui/square-plus'
import StrikethroughSvg from '~icons/gravity-ui/strikethrough'
import SunSvg from '~icons/gravity-ui/sun'
import TargetSvg from '~icons/gravity-ui/target'
import TargetDartSvg from '~icons/gravity-ui/target-dart'
import TerminalSvg from '~icons/gravity-ui/terminal'
import TextSvg from '~icons/gravity-ui/text'
import ThumbsDownSvg from '~icons/gravity-ui/thumbs-down'
import ThumbsDownFillSvg from '~icons/gravity-ui/thumbs-down-fill'
import ThumbsUpSvg from '~icons/gravity-ui/thumbs-up'
import ThumbsUpFillSvg from '~icons/gravity-ui/thumbs-up-fill'
import ThunderboltSvg from '~icons/gravity-ui/thunderbolt'
import ThunderboltFillSvg from '~icons/gravity-ui/thunderbolt-fill'
import TrashBinSvg from '~icons/gravity-ui/trash-bin'
import TriangleExclamationSvg from '~icons/gravity-ui/triangle-exclamation'
import TriangleExclamationFillSvg from '~icons/gravity-ui/triangle-exclamation-fill'
import UnderlineSvg from '~icons/gravity-ui/underline'
import XmarkSvg from '~icons/gravity-ui/xmark'

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

export const ArrowDown = /* @__PURE__ */ icon(ArrowDownSvg)
export const ArrowRight = /* @__PURE__ */ icon(ArrowRightSvg)
export const ArrowUp = /* @__PURE__ */ icon(ArrowUpSvg)
export const Bold = /* @__PURE__ */ icon(BoldSvg)
export const Bookmark = /* @__PURE__ */ icon(BookmarkSvg, BookmarkFillSvg)
export const Bot = /* @__PURE__ */ icon(FaceRobotSvg)
export const BriefcaseBusiness = /* @__PURE__ */ icon(BriefcaseSvg, BriefcaseFillSvg)
export const CalendarClock = /* @__PURE__ */ icon(ClockSvg, ClockFillSvg)
export const Captions = /* @__PURE__ */ icon(TextSvg)
export const Check = /* @__PURE__ */ icon(CheckSvg)
export const ChevronDown = /* @__PURE__ */ icon(ChevronDownSvg)
export const ChevronRight = /* @__PURE__ */ icon(ChevronRightSvg)
export const ChevronLeft = /* @__PURE__ */ icon(ChevronLeftSvg)
export const ChevronUp = /* @__PURE__ */ icon(ChevronUpSvg)
export const CircleAlert = /* @__PURE__ */ icon(CircleExclamationSvg, CircleExclamationFillSvg)
export const CircleCheck = /* @__PURE__ */ icon(CircleCheckSvg, CircleCheckFillSvg)
export const Clapperboard = /* @__PURE__ */ icon(FilmstripSvg)
export const Code = /* @__PURE__ */ icon(CodeSvg)
export const Compass = /* @__PURE__ */ icon(CompassSvg)
export const Download = /* @__PURE__ */ icon(ArrowDownToLineSvg)
export const ExternalLink = /* @__PURE__ */ icon(ArrowUpRightFromSquareSvg)
export const Eye = /* @__PURE__ */ icon(EyeSvg)
export const EyeOff = /* @__PURE__ */ icon(EyeSlashSvg)
export const FilePen = /* @__PURE__ */ icon(PencilToSquareSvg)
export const FileText = /* @__PURE__ */ icon(FileTextSvg)
export const Heading2 = /* @__PURE__ */ icon(Heading2Svg)
export const Heart = /* @__PURE__ */ icon(HeartSvg, HeartFillSvg)
export const ImageOff = /* @__PURE__ */ icon(PictureSvg)
export const Info = /* @__PURE__ */ icon(CircleInfoSvg, CircleInfoFillSvg)
export const Italic = /* @__PURE__ */ icon(ItalicSvg)
export const KeyRound = /* @__PURE__ */ icon(KeySvg)
export const Layers = /* @__PURE__ */ icon(LayersSvg)
export const Link2 = /* @__PURE__ */ icon(LinkSvg)
export const List = /* @__PURE__ */ icon(ListUlSvg)
export const ListOrdered = /* @__PURE__ */ icon(ListOlSvg)
export const Loader2 = /* @__PURE__ */ icon(ArrowsRotateRightSvg)
export const LogIn = /* @__PURE__ */ icon(ArrowRightToSquareSvg)
export const LogOut = /* @__PURE__ */ icon(ArrowRightFromSquareSvg)
export const Mic = /* @__PURE__ */ icon(MicrophoneSvg)
export const Minus = /* @__PURE__ */ icon(MinusSvg)
export const Moon = /* @__PURE__ */ icon(MoonSvg)
export const OctagonX = /* @__PURE__ */ icon(OctagonXmarkSvg)
export const PenLine = /* @__PURE__ */ icon(PencilSvg)
export const Plus = /* @__PURE__ */ icon(PlusSvg)
export const Quote = /* @__PURE__ */ icon(QuoteOpenSvg)
export const Radar = /* @__PURE__ */ icon(TargetDartSvg)
export const RefreshCw = /* @__PURE__ */ icon(ArrowsRotateRightSvg)
export const RotateCcw = /* @__PURE__ */ icon(ArrowRotateLeftSvg)
export const RotateCw = /* @__PURE__ */ icon(ArrowRotateRightSvg)
export const Rss = /* @__PURE__ */ icon(BroadcastSignalSvg)
export const Save = /* @__PURE__ */ icon(FloppyDiskSvg)
export const ScanText = /* @__PURE__ */ icon(FileMagnifierSvg)
export const Search = /* @__PURE__ */ icon(MagnifierSvg)
export const Send = /* @__PURE__ */ icon(PaperPlaneSvg)
export const Settings2 = /* @__PURE__ */ icon(GearSvg)
export const ShieldCheck = /* @__PURE__ */ icon(ShieldCheckSvg)
export const SlidersHorizontal = /* @__PURE__ */ icon(SlidersSvg)
export const Sparkles = /* @__PURE__ */ icon(SparklesSvg, SparklesFillSvg)
export const Strikethrough = /* @__PURE__ */ icon(StrikethroughSvg)
export const Sun = /* @__PURE__ */ icon(SunSvg)
export const Target = /* @__PURE__ */ icon(TargetSvg)
export const ThumbsDown = /* @__PURE__ */ icon(ThumbsDownSvg, ThumbsDownFillSvg)
export const ThumbsUp = /* @__PURE__ */ icon(ThumbsUpSvg, ThumbsUpFillSvg)
export const Trash2 = /* @__PURE__ */ icon(TrashBinSvg)
export const TriangleAlert = /* @__PURE__ */ icon(
  TriangleExclamationSvg,
  TriangleExclamationFillSvg,
)
export const Underline = /* @__PURE__ */ icon(UnderlineSvg)
export const UserPlus = /* @__PURE__ */ icon(PersonPlusSvg)
export const Users = /* @__PURE__ */ icon(PersonsSvg)
export const X = /* @__PURE__ */ icon(XmarkSvg)
export const Newspaper = /* @__PURE__ */ icon(SquareArticleSvg)
export const DynamicFeed = /* @__PURE__ */ icon(LayoutListSvg)
export const CompareArrows = /* @__PURE__ */ icon(ArrowRightArrowLeftSvg)
export const Schedule = /* @__PURE__ */ icon(ClockSvg, ClockFillSvg)
export const ContentCopy = /* @__PURE__ */ icon(CopySvg)
export const Hub = /* @__PURE__ */ icon(NodesDownSvg)
export const CalendarMonth = /* @__PURE__ */ icon(CalendarSvg)
export const Terminal = /* @__PURE__ */ icon(TerminalSvg)
export const Account = /* @__PURE__ */ icon(PersonSvg, PersonFillSvg)
export const GitCompareArrows = /* @__PURE__ */ icon(CodeCompareSvg)
export const Shield = /* @__PURE__ */ icon(ShieldSvg)
export const Factory = /* @__PURE__ */ icon(FactorySvg)
export const ElectricBolt = /* @__PURE__ */ icon(ThunderboltSvg, ThunderboltFillSvg)
export const Dns = /* @__PURE__ */ icon(ServerSvg)
export const Cloud = /* @__PURE__ */ icon(CloudSvg)
export const Memory = /* @__PURE__ */ icon(CpuSvg)
export const Router = /* @__PURE__ */ icon(AntennaSignalSvg)
export const Database = /* @__PURE__ */ icon(DatabaseSvg, DatabaseFillSvg)
export const Policy = /* @__PURE__ */ icon(ShieldKeyholeSvg)
export const Gavel = /* @__PURE__ */ icon(ScalesBalancedSvg)
export const Analytics = /* @__PURE__ */ icon(ChartColumnSvg)
export const RocketLaunch = /* @__PURE__ */ icon(RocketSvg)
export const BugReport = /* @__PURE__ */ icon(BugSvg)
export const Lock = /* @__PURE__ */ icon(LockSvg, LockFillSvg)
export const Psychology = /* @__PURE__ */ icon(BulbSvg)
export const School = /* @__PURE__ */ icon(GraduationCapSvg)
export const SatelliteAlt = /* @__PURE__ */ icon(SignalSvg)
export const Language = /* @__PURE__ */ icon(GlobeSvg)
export const Palette = /* @__PURE__ */ icon(PaletteSvg)
export const FileUp = /* @__PURE__ */ icon(FileArrowUpSvg)
export const Share = /* @__PURE__ */ icon(ArrowShapeTurnUpRightSvg)
export const LinkOff = /* @__PURE__ */ icon(LinkSlashSvg)
export const Colorize = /* @__PURE__ */ icon(DropletSvg)
export const LibraryAdd = /* @__PURE__ */ icon(SquarePlusSvg)
export const AutoAwesome = /* @__PURE__ */ icon(MagicWandSvg)
export const TrendingUp = /* @__PURE__ */ icon(ChartLineArrowUpSvg)
export const TrendingDown = /* @__PURE__ */ icon(ArrowDownRightSvg)
export const Block = /* @__PURE__ */ icon(BanSvg)
export const Camera = /* @__PURE__ */ icon(CameraSvg)
export const EventRepeat = /* @__PURE__ */ icon(ArrowsRotateLeftSvg)
export const Help = /* @__PURE__ */ icon(CircleQuestionSvg, CircleQuestionFillSvg)

// The names shadcn components import.
export const CheckIcon = Check
export const XIcon = X
export const ChevronDownIcon = ChevronDown
export const ChevronLeftIcon = ChevronLeft
export const ChevronRightIcon = ChevronRight
export const ChevronUpIcon = ChevronUp
export const InfoIcon = Info
export const TriangleAlertIcon = TriangleAlert
export const CircleCheckIcon = CircleCheck
export const OctagonXIcon = OctagonX
export const Loader2Icon = Loader2
export const BotIcon = Bot
