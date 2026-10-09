import { AnimateView } from 'motion/react-animate-view'
import type { ReactNode } from 'react'
import { Segmented } from '../../components/Segmented'
import type { Audience, DigestSummary } from '../../lib/api'
import { formatPeriod } from '../../lib/format'

// The name a digest's title carries while it moves between the history list
// and the page header. One element has it at a time: the header for the open
// digest, the list row for every other one.
const titleView = (digestId: string) => `digest-title-${digestId}`

// A soft spring for the morph: long enough to follow, short enough not to wait for.
const MORPH = { type: 'spring', bounce: 0.14, visualDuration: 0.45 } as const

/** The title, named for the morph between the list and the header. */
export function MorphingTitle({ digestId, children }: { digestId: string; children: ReactNode }) {
  return (
    <AnimateView name={titleView(digestId)} share={{ transition: MORPH }}>
      {children}
    </AnimateView>
  )
}

/**
 * The open digest's header, drawn from the history list, which is already
 * loaded: it is there in the very render that opens the digest, so its title
 * grows out of the list row while the rest of the digest is still loading.
 */
const READINGS = [
  { value: 'specialist', label: 'Инженер', short: 'Инженер' },
  { value: 'management', label: 'Руководитель', short: 'Руководитель' },
] as const satisfies readonly { value: Audience; label: string; short: string }[]

type HeadingProps = {
  summary: DigestSummary
  /** The other audience's issue of the same build, when there is one. */
  twin?: DigestSummary | null
  onOpen?: (id: string) => void
}

export function DigestHeading({ summary, twin, onOpen }: HeadingProps) {
  return (
    <div className="rounded-3xl bg-accent-soft px-6 py-6 text-accent-soft-foreground sm:px-8">
      <p className="text-xs font-medium opacity-80">
        {summary.profile_name} · версия {summary.profile_version} ·{' '}
        {formatPeriod(summary.period_start, summary.period_end)}
      </p>
      <MorphingTitle digestId={summary.id}>
        <h1 className="mt-2 font-serif text-[26px] leading-tight font-semibold tracking-tight text-balance sm:text-[30px]">
          {summary.title ?? summary.profile_name}
        </h1>
      </MorphingTitle>
      {twin && onOpen && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Segmented
            label="Для кого читать выпуск"
            value={summary.audience ?? 'specialist'}
            options={READINGS}
            onChange={(audience) => {
              if (audience !== (summary.audience ?? 'specialist')) onOpen(twin.id)
            }}
            className="bg-surface/70"
          />
          <span className="text-xs opacity-80">те же новости, другой язык</span>
        </div>
      )}
    </div>
  )
}
