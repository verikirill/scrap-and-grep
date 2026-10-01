import { cn } from '../lib/utils'

/**
 * The brand mark: the cat with a news sheet and a magnifier. It sits on a
 * light tile in both themes: the cat is black and would vanish on a dark
 * surface otherwise.
 */
export function LogoMark({ size = 40, className }: { size?: number; className?: string }) {
  const image = Math.round(size * 0.86)
  return (
    <span
      className={cn(
        'grid shrink-0 place-items-center overflow-hidden bg-white shadow-elevation-1 ring-1 ring-black/5',
        className,
      )}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.3) }}
    >
      <img
        src="/brand/mark.webp"
        srcSet="/brand/mark.webp 1x, /brand/mark@2x.webp 2x"
        alt=""
        width={image}
        height={image}
        decoding="async"
        draggable={false}
      />
    </span>
  )
}

/** The name, with its ampersand in the accent colour. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('font-semibold tracking-tight', className)}>
      Tail<span className="text-primary">&amp;</span>Grep
    </span>
  )
}
