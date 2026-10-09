import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { ChevronDown, ExternalLink, Layers } from '../../components/icons'
import { DURATION, EASE } from '../../components/tokens'
import type { Duplicate } from '../../lib/api'
import { externalHref, plural } from '../../lib/format'
import { initials, sourceTint } from '../feed/sourceLook'

// More faces than this read as a smear; the rest is a number.
const FACES = 5

/** A stable number for a name, so an outlet keeps its colour across entries. */
function nameSeed(name: string): number {
  let seed = 0
  for (const char of name) seed = (seed * 31 + char.charCodeAt(0)) | 0
  return seed
}

/**
 * The outlets that told the same story, merged into this entry: their badges
 * in a stack that fans out on hover, and the list of their own headlines.
 */
export function StoryStack({ main, duplicates }: { main: string; duplicates: Duplicate[] }) {
  const [isOpen, setOpen] = useState(false)
  const [isFanned, setFanned] = useState(false)
  if (duplicates.length === 0) return null
  const names = [main, ...duplicates.map((duplicate) => duplicate.source_name)]
  const outlets = [...new Set(names)]
  const shown = outlets.slice(0, FACES)
  const count = duplicates.length + 1
  return (
    <div className="mt-2.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        onPointerEnter={() => setFanned(true)}
        onPointerLeave={() => setFanned(false)}
        aria-expanded={isOpen}
        className="inline-flex items-center gap-2.5 rounded-full py-1 pr-3 pl-1 text-xs transition-colors hover:bg-default/60"
      >
        <span className="flex items-center">
          {shown.map((name, index) => (
            <motion.span
              key={name}
              aria-hidden
              animate={{
                marginLeft: index === 0 ? 0 : isFanned ? 3 : -8,
                rotate: isFanned ? 0 : (index - 1) * 4,
              }}
              transition={{ type: 'spring', stiffness: 420, damping: 28 }}
              className="grid size-6 place-items-center rounded-full text-[10px] font-semibold ring-2 ring-surface"
              style={{
                background: `var(--tag-${sourceTint(nameSeed(name))})`,
                color: `var(--on-tag-${sourceTint(nameSeed(name))})`,
                zIndex: FACES - index,
              }}
            >
              {initials(name)}
            </motion.span>
          ))}
          {outlets.length > FACES && (
            <span className="ml-1 text-muted">+{outlets.length - FACES}</span>
          )}
        </span>
        <span className="font-medium text-foreground">
          Сюжет из {count} {plural(count, ['публикации', 'публикаций', 'публикаций'])}
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={14} className="text-muted" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: DURATION.medium, ease: EASE }}
            className="ml-3 overflow-hidden border-l-2 border-separator"
          >
            {duplicates.map((duplicate, index) => (
              <motion.li
                key={duplicate.url}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2, delay: 0.05 + index * 0.04 }}
                className="py-1 pl-3"
              >
                <a
                  href={externalHref(duplicate.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-start gap-1.5 text-[13px]"
                >
                  <Layers size={13} className="mt-1 shrink-0 text-muted" />
                  <span className="min-w-0">
                    <span className="font-medium text-foreground group-hover:text-accent">
                      {duplicate.source_name}
                    </span>
                    <span className="text-muted"> · {duplicate.title}</span>
                  </span>
                  <ExternalLink
                    size={12}
                    className="mt-1 shrink-0 text-muted opacity-0 group-hover:opacity-100"
                  />
                </a>
              </motion.li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}
