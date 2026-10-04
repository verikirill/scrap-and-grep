import type { DigestSummary } from './api'

type Kind = Pick<DigestSummary, 'id' | 'profile_id' | 'audience'>

/**
 * Two issues worth comparing: the same profile written for the same audience.
 * The pair of one «Собрать оба выпуска» build shares its selection, so set side
 * by side it would always read as "nothing changed".
 */
export function sameKind(a: Kind, b: Kind): boolean {
  return (
    a.id !== b.id &&
    a.profile_id === b.profile_id &&
    (a.audience ?? 'specialist') === (b.audience ?? 'specialist')
  )
}
