import clsx from 'clsx'
import { initials, sourceTint } from './sourceLook'

type Props = { sourceId: number; name: string; className?: string }

/** A round avatar with the source's initials in its colour. Decorative: the name is next to it. */
export function SourceAvatar({ sourceId, name, className }: Props) {
  const tint = sourceTint(sourceId)
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-full font-semibold tracking-tight select-none',
        className,
      )}
      style={{ background: `var(--md-tag-${tint})`, color: `var(--md-on-tag-${tint})` }}
    >
      {initials(name)}
    </span>
  )
}
