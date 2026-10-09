import type { DigestSummary } from './api'

type Kind = Pick<DigestSummary, 'id' | 'profile_id' | 'audience'>

/**
 * Two issues worth comparing: the same profile written for the same audience.
 * The pair of one «Специалисту и руководству» build shares its selection, so set side
 * by side it would always read as "nothing changed".
 */
export function sameKind(a: Kind, b: Kind): boolean {
  return (
    a.id !== b.id &&
    a.profile_id === b.profile_id &&
    (a.audience ?? 'specialist') === (b.audience ?? 'specialist')
  )
}

type Twin = Kind & Pick<DigestSummary, 'period_start' | 'period_end' | 'status'>

/**
 * The other audience's issue of the same build: one profile, the other
 * audience, the very same period. «Специалисту и руководству» writes the two
 * over one period, so the reader can switch between the engineer's and the
 * manager's reading of the same news. Unfinished twins do not count.
 */
export function twinOf<T extends Twin>(digest: T, digests: readonly T[]): T | null {
  const audience = digest.audience ?? 'specialist'
  return (
    digests.find(
      (other) =>
        other.id !== digest.id &&
        other.profile_id === digest.profile_id &&
        (other.audience ?? 'specialist') !== audience &&
        other.period_start === digest.period_start &&
        other.period_end === digest.period_end &&
        other.status === 'done',
    ) ?? null
  )
}
