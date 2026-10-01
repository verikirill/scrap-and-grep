import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { Slider as SliderPrimitive } from 'radix-ui'
import { createElement, useEffect, useEffectEvent, useRef, useState } from 'react'
import { Check, Colorize, Palette } from '../../components/icons'
import { EASE } from '../../components/tokens'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover'
import { useRadioKeys } from '../../components/useRadioKeys'
import type { Profile } from '../../lib/api'
import {
  PROFILE_COLORS,
  PROFILE_ICONS,
  colorOf,
  hueAndChroma,
  isCustomColor,
  profileColors,
  profileIcon,
  swatchColor,
} from '../../lib/profileLook'
import { keys, useSetProfileLook } from '../../lib/queries'

type Look = Pick<Profile, 'icon' | 'color'> & { spec: Pick<Profile['spec'], 'name'> }

/** A profile's tile: its icon on its colour, or its first letter while it has no icon. */
export function ProfileAvatar({
  profile,
  size = 40,
  className,
}: {
  profile: Look
  size?: number
  className?: string
}) {
  // A component from the fixed list, not one made here: drawn with createElement.
  const icon = profileIcon(profile.icon)
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-full font-semibold transition-colors duration-300',
        className,
      )}
      style={{ width: size, height: size, ...profileColors(profile.color) }}
    >
      {icon ? (
        createElement(icon, { size: Math.round(size * 0.55), filled: true })
      ) : (
        <span style={{ fontSize: Math.round(size * 0.4) }}>
          {profile.spec.name.slice(0, 1).toUpperCase()}
        </span>
      )}
    </span>
  )
}

const CHROMA_MAX = 80
const FALLBACK = { hue: 200, chroma: 48 }
// A slider moves the colour at once; the server hears of it when the hand stops.
const SAVE_DELAY_MS = 400
// Equal steps of hue at one tone and colourfulness: the track has no bright
// or dark bands that are not in the colours themselves.
const HUE_STOPS = Array.from({ length: 13 }, (_, step) => colorOf(step * 30, 48)).join(', ')
const CUSTOM = 'custom'
const COLOR_CHOICES = [...PROFILE_COLORS.map((item) => item.key), CUSTOM]
// The dots are 32 px; the area that takes a tap is 44.
const TAP_AREA = "relative after:absolute after:-inset-1.5 after:content-['']"

/** Where the custom picker starts: the reader's colour, or the palette colour they leave. */
function startingPoint(color: string | null): { hue: number; chroma: number } {
  if (isCustomColor(color)) return hueAndChroma(color)
  const dot = getComputedStyle(document.documentElement)
    .getPropertyValue(`--md-swatch-${color ?? 'blue'}`)
    .trim()
    .toLowerCase()
  return isCustomColor(dot) ? hueAndChroma(dot) : FALLBACK
}

function ColorSlider({
  label,
  value,
  max,
  track,
  thumb,
  onChange,
  onCommit,
}: {
  label: string
  value: number
  max: number
  track: string
  thumb: string
  onChange: (value: number) => void
  onCommit: (value: number) => void
}) {
  return (
    <div>
      <p className="mb-1 text-xs text-on-surface-variant">{label}</p>
      <SliderPrimitive.Root
        value={[value]}
        min={0}
        max={max}
        step={1}
        onValueChange={([next]) => onChange(next)}
        onValueCommit={([next]) => onCommit(next)}
        className="relative flex h-7 w-full touch-none items-center select-none"
      >
        <SliderPrimitive.Track
          className="relative h-3 grow rounded-full shadow-[inset_0_0_0_1px_rgb(0_0_0/0.08)]"
          style={{ background: track }}
        />
        <SliderPrimitive.Thumb
          aria-label={label}
          className="block size-6 rounded-full border-[3px] border-white shadow-elevation-2 ring-1 ring-black/15 transition-transform duration-150 outline-none hover:scale-110 focus-visible:ring-4 focus-visible:ring-primary/45 active:scale-110"
          style={{ background: thumb }}
        />
      </SliderPrimitive.Root>
    </div>
  )
}

/** Hue and colourfulness of one's own colour, or its code. Tones come from the palette rules. */
function CustomColor({ profile, onPick }: { profile: Profile; onPick: (color: string) => void }) {
  const [draft, setDraft] = useState(() => {
    const start = startingPoint(profile.color)
    const hex = isCustomColor(profile.color) ? profile.color : colorOf(start.hue, start.chroma)
    return { ...start, hex }
  })
  const [code, setCode] = useState(draft.hex)
  const isValid = isCustomColor(code)

  const slide = (hue: number, chroma: number) => {
    const hex = colorOf(hue, chroma)
    setDraft({ hue, chroma, hex })
    setCode(hex)
    return hex
  }
  const type = (text: string) => {
    const value = (text.startsWith('#') ? text : `#${text}`).trim().toLowerCase()
    setCode(value)
    if (!isCustomColor(value)) return
    setDraft({ ...hueAndChroma(value), hex: value })
    onPick(value)
  }

  return (
    <div className="space-y-2 px-1 pt-3 pb-1">
      <div className="flex items-center gap-3">
        <ProfileAvatar profile={{ ...profile, color: draft.hex }} size={40} />
        <label
          className={clsx(
            'flex h-10 flex-1 items-center gap-1 rounded-xl bg-surface-container-high px-3 font-mono text-sm focus-within:outline-2',
            isValid ? 'focus-within:outline-primary' : 'outline-2 outline-destructive',
          )}
        >
          <span className="sr-only">Код цвета</span>
          <input
            value={code}
            onChange={(event) => type(event.target.value)}
            maxLength={7}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={!isValid}
            className="w-full min-w-0 bg-transparent uppercase outline-none"
          />
        </label>
      </div>
      <ColorSlider
        label="Оттенок"
        value={draft.hue}
        max={360}
        track={`linear-gradient(to right, ${HUE_STOPS})`}
        thumb={draft.hex}
        onChange={(hue) => slide(hue, draft.chroma)}
        onCommit={(hue) => onPick(slide(hue, draft.chroma))}
      />
      <ColorSlider
        label="Насыщенность"
        value={Math.min(draft.chroma, CHROMA_MAX)}
        max={CHROMA_MAX}
        track={`linear-gradient(to right, ${colorOf(draft.hue, 0)}, ${colorOf(draft.hue, CHROMA_MAX)})`}
        thumb={draft.hex}
        onChange={(chroma) => slide(draft.hue, chroma)}
        onCommit={(chroma) => onPick(slide(draft.hue, chroma))}
      />
    </div>
  )
}

/** The tile as a button that opens the choice of icon and colour. */
export function ProfileLookPicker({ profile }: { profile: Profile }) {
  const [isOpen, setOpen] = useState(false)
  const client = useQueryClient()
  const setLook = useSetProfileLook()
  const pending = useRef<{ timer: number; color: string } | null>(null)
  const isCustom = isCustomColor(profile.color)

  // The other half of the look comes from the cache, where picks still on
  // their way already are: a late colour must not bring back an old icon.
  const pick = (patch: Partial<Pick<Profile, 'icon' | 'color'>>) => {
    const now =
      client.getQueryData<Profile[]>(keys.profiles)?.find((item) => item.id === profile.id) ??
      profile
    setLook.mutate({
      id: profile.id,
      icon: patch.icon !== undefined ? patch.icon : now.icon,
      color: patch.color !== undefined ? patch.color : now.color,
    })
  }
  const cancelPending = () => {
    if (pending.current) window.clearTimeout(pending.current.timer)
    pending.current = null
  }
  const flush = () => {
    const waiting = pending.current
    cancelPending()
    if (waiting) pick({ color: waiting.color })
  }
  const pickSoon = (color: string) => {
    cancelPending()
    pending.current = { color, timer: window.setTimeout(flush, SAVE_DELAY_MS) }
  }
  const chooseColor = (key: string) => {
    // A dot clicked over a moving slider wins: the slider's save is dropped.
    cancelPending()
    if (key !== CUSTOM) return pick({ color: key })
    if (isCustom) return
    const start = startingPoint(profile.color)
    pick({ color: colorOf(start.hue, start.chroma) })
  }

  // Leaving the page with a colour not yet sent sends it.
  const sendPending = useEffectEvent(flush)
  useEffect(() => () => sendPending(), [])

  const iconKeys = useRadioKeys(
    PROFILE_ICONS.length,
    PROFILE_ICONS.findIndex((item) => item.key === profile.icon),
    (index) => pick({ icon: PROFILE_ICONS[index].key }),
  )
  const colorKeys = useRadioKeys(
    COLOR_CHOICES.length,
    isCustom ? COLOR_CHOICES.length - 1 : COLOR_CHOICES.indexOf(profile.color ?? 'blue'),
    (index) => chooseColor(COLOR_CHOICES[index]),
  )

  return (
    <Popover
      open={isOpen}
      onOpenChange={(next) => {
        if (!next) flush()
        setOpen(next)
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Значок и цвет профиля"
          title="Значок и цвет профиля"
          className="group relative rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <ProfileAvatar profile={profile} size={48} />
          <span className="absolute -right-1 -bottom-1 grid size-6 place-items-center rounded-full bg-surface-container-highest text-on-surface-variant shadow-elevation-1 transition-transform duration-300 group-hover:scale-110">
            <Palette size={14} />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        collisionPadding={12}
        // On a phone the tile sits low: the picker scrolls inside rather than
        // running off the top of the screen.
        className="max-h-(--radix-popover-content-available-height) w-[296px] overflow-y-auto overscroll-contain rounded-3xl p-4"
      >
        <p className="mb-2 text-xs font-medium text-on-surface-variant">Значок</p>
        <div
          role="radiogroup"
          aria-label="Значок профиля"
          className="grid grid-cols-6 gap-1.5"
          onKeyDown={iconKeys.onKeyDown}
        >
          {PROFILE_ICONS.map(({ key, label, icon: Icon }, index) => {
            const isChosen = profile.icon === key
            return (
              <button
                key={key}
                {...iconKeys.itemProps(index)}
                type="button"
                role="radio"
                aria-checked={isChosen}
                aria-label={label}
                title={label}
                onClick={() => pick({ icon: key })}
                className={clsx(
                  'relative grid size-10 place-items-center rounded-xl transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-primary',
                  isChosen
                    ? 'text-primary-foreground'
                    : 'text-on-surface-variant hover:bg-surface-container-high',
                )}
              >
                {isChosen && (
                  <motion.span
                    layoutId="look-icon"
                    className="absolute inset-0 rounded-xl bg-primary"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  />
                )}
                <Icon size={22} filled={isChosen} className="relative" />
              </button>
            )
          })}
        </div>
        <p className="mt-4 mb-2 text-xs font-medium text-on-surface-variant">Цвет</p>
        <div
          role="radiogroup"
          aria-label="Цвет профиля"
          className="flex flex-wrap gap-2"
          onKeyDown={colorKeys.onKeyDown}
        >
          {PROFILE_COLORS.map(({ key, label }, index) => {
            const isChosen = !isCustom && (profile.color ?? 'blue') === key
            return (
              <button
                key={key}
                {...colorKeys.itemProps(index)}
                type="button"
                role="radio"
                aria-checked={isChosen}
                aria-label={label}
                title={label}
                onClick={() => chooseColor(key)}
                className={clsx(
                  TAP_AREA,
                  'grid size-8 place-items-center rounded-full text-white ring-offset-2 ring-offset-popover transition-shadow duration-200 dark:text-black',
                  isChosen ? 'ring-2 ring-primary' : 'hover:ring-2 hover:ring-outline-variant',
                )}
                style={{ background: swatchColor(key) }}
              >
                {isChosen && <Check size={16} />}
              </button>
            )
          })}
          <button
            {...colorKeys.itemProps(COLOR_CHOICES.length - 1)}
            type="button"
            role="radio"
            aria-checked={isCustom}
            aria-label="Свой цвет"
            title="Свой цвет"
            onClick={() => chooseColor(CUSTOM)}
            className={clsx(
              TAP_AREA,
              'grid size-8 place-items-center rounded-full text-white ring-offset-2 ring-offset-popover transition-shadow duration-200',
              isCustom
                ? 'ring-2 ring-primary dark:text-black'
                : 'hover:ring-2 hover:ring-outline-variant',
            )}
            style={{
              background:
                isCustom && profile.color
                  ? swatchColor(profile.color)
                  : `conic-gradient(from 90deg, ${HUE_STOPS})`,
            }}
          >
            {isCustom ? (
              <Check size={16} />
            ) : (
              <Colorize size={15} className="drop-shadow-[0_1px_1px_rgb(0_0_0/0.45)]" />
            )}
          </button>
        </div>
        <AnimatePresence initial={false}>
          {isCustom && (
            <motion.div
              key="custom"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.28, ease: EASE }}
              className="overflow-hidden"
            >
              <CustomColor profile={profile} onPick={pickSoon} />
            </motion.div>
          )}
        </AnimatePresence>
      </PopoverContent>
    </Popover>
  )
}
