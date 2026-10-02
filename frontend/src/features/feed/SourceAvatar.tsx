import clsx from 'clsx'
import { useState } from 'react'
import { API_BASE } from '../../lib/api'
import { useSourceAvatars } from '../../lib/queries'
import { initials, sourceTint } from './sourceLook'

type Props = { sourceId: number; name: string; className?: string }

/**
 * A round avatar: the source's picture (a channel's avatar, a site's icon) when
 * the server has one, its initials in its colour until then or if it fails.
 * Decorative: the name is next to it.
 */
export function SourceAvatar({ sourceId, name, className }: Props) {
  const version = useSourceAvatars().data?.[sourceId]
  const [isBroken, setIsBroken] = useState(false)
  const tint = sourceTint(sourceId)
  const classes = clsx(
    'grid shrink-0 place-items-center overflow-hidden rounded-full font-semibold tracking-tight select-none',
    className,
  )
  if (version && !isBroken) {
    return (
      <span aria-hidden className={clsx(classes, 'bg-white ring-1 ring-outline-variant/60')}>
        <img
          src={`${API_BASE}/sources/${sourceId}/avatar?v=${version}`}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setIsBroken(true)}
          className="size-full object-contain"
        />
      </span>
    )
  }
  return (
    <span
      aria-hidden
      className={classes}
      style={{ background: `var(--md-tag-${tint})`, color: `var(--md-on-tag-${tint})` }}
    >
      {initials(name)}
    </span>
  )
}
