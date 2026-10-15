import clsx from 'clsx'
import { useState } from 'react'
import type { Me } from '../lib/api'
import { nameHue, nameInitials } from '../lib/avatar'

type Props = {
  me: Pick<Me, 'display_name' | 'avatar_url'> & Partial<Pick<Me, 'is_demo'>>
  size: number
  className?: string
}

/**
 * The reader's picture, or their initials on a soft gradient of a hue of
 * their own while there is none: two readers without a picture look apart.
 * A guest without a picture gets the guest character instead of a letter.
 */
export function UserAvatar({ me, size, className }: Props) {
  // A picture that failed to load falls back to the initials, until a new one is set.
  const [broken, setBroken] = useState<string | null>(null)
  if (me.avatar_url && broken !== me.avatar_url) {
    return (
      <img
        src={me.avatar_url}
        alt=""
        width={size}
        height={size}
        decoding="async"
        onError={() => setBroken(me.avatar_url)}
        className={clsx('shrink-0 rounded-full object-cover', className)}
        style={{ width: size, height: size }}
      />
    )
  }
  if (me.is_demo) {
    return (
      <img
        src="/brand/guest.webp"
        srcSet="/brand/guest.webp 1x, /brand/guest@2x.webp 2x"
        alt=""
        width={size}
        height={size}
        decoding="async"
        draggable={false}
        className={clsx('shrink-0 rounded-full object-cover', className)}
        style={{ width: size, height: size }}
      />
    )
  }
  const hue = nameHue(me.display_name)
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-full leading-none font-semibold tracking-tight text-white select-none',
        'shadow-[inset_0_0_0_1px_rgb(255_255_255/0.22),inset_0_1px_0_rgb(255_255_255/0.25)]',
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.38),
        background: `linear-gradient(135deg, oklch(0.74 0.13 ${hue}), oklch(0.55 0.17 ${(hue + 45) % 360}))`,
        textShadow: '0 1px 2px rgb(0 0 0 / 0.18)',
      }}
    >
      {nameInitials(me.display_name)}
    </span>
  )
}
