import clsx from 'clsx'
import { motion } from 'motion/react'
import { createElement, useState } from 'react'
import { Check, Palette } from '../../components/icons'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover'
import type { Profile } from '../../lib/api'
import {
  PROFILE_COLORS,
  PROFILE_ICONS,
  profileColors,
  profileIcon,
  swatchColor,
} from '../../lib/profileLook'
import { useSetProfileLook } from '../../lib/queries'

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

/** The tile as a button that opens the choice of icon and colour. */
export function ProfileLookPicker({ profile }: { profile: Profile }) {
  const [isOpen, setOpen] = useState(false)
  const setLook = useSetProfileLook()
  const pick = (patch: Partial<Pick<Profile, 'icon' | 'color'>>) =>
    setLook.mutate({
      id: profile.id,
      icon: patch.icon !== undefined ? patch.icon : profile.icon,
      color: patch.color !== undefined ? patch.color : profile.color,
    })

  return (
    <Popover open={isOpen} onOpenChange={setOpen}>
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
      <PopoverContent align="start" className="w-[296px] rounded-3xl p-4">
        <p className="mb-2 text-xs font-medium text-on-surface-variant">Значок</p>
        <div role="radiogroup" aria-label="Значок профиля" className="grid grid-cols-6 gap-1.5">
          {PROFILE_ICONS.map(({ key, label, icon: Icon }) => {
            const isChosen = profile.icon === key
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={isChosen}
                aria-label={label}
                title={label}
                onClick={() => pick({ icon: key })}
                className={clsx(
                  'relative grid size-10 place-items-center rounded-xl transition-colors duration-200',
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
        <div role="radiogroup" aria-label="Цвет профиля" className="flex flex-wrap gap-2">
          {PROFILE_COLORS.map(({ key, label }) => {
            const isChosen = (profile.color ?? 'blue') === key

            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={isChosen}
                aria-label={label}
                title={label}
                onClick={() => pick({ color: key })}
                className={clsx(
                  'grid size-8 place-items-center rounded-full text-white ring-offset-2 ring-offset-popover transition-shadow duration-200 dark:text-black',
                  isChosen ? 'ring-2 ring-primary' : 'hover:ring-2 hover:ring-outline-variant',
                )}
                style={{ background: swatchColor(key) }}
              >
                {isChosen && <Check size={16} />}
              </button>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
