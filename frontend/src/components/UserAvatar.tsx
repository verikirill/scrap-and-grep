import clsx from 'clsx'
import { useState } from 'react'
import type { Me } from '../lib/api'

type Props = {
  me: Pick<Me, 'display_name' | 'avatar_url'>
  size: number
  className?: string
}

/** The reader's picture, or the first letter of their name while there is none. */
export function UserAvatar({ me, size, className }: Props) {
  // A picture that failed to load falls back to the letter, until a new one is set.
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
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-full font-semibold select-none',
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4) }}
    >
      {me.display_name.slice(0, 1).toUpperCase()}
    </span>
  )
}
