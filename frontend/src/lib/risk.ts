import type { DigestItem } from './api'

/** 0, 1 or 2: low to high on one axis of the risk matrix. */
export type Band = 0 | 1 | 2

/** The CVSS score an entry is known by: the highest its card or the bases give. */
export function cvssOf(item: DigestItem): number | null {
  const scores = [
    item.vulnerability?.cvss_score,
    ...(item.references ?? []).flatMap((reference) => [reference.nvd_cvss, reference.bdu_cvss]),
  ]
    .map((value) => Number.parseFloat(String(value ?? '').replace(',', '.')))
    .filter((value) => Number.isFinite(value) && value >= 0 && value <= 10)
  return scores.length > 0 ? Math.max(...scores) : null
}

/** Exploited already: in CISA KEV, used in attacks per the BDU, or "in the wild" in the card. */
function isExploited(item: DigestItem): boolean {
  return (
    item.vulnerability?.exploit === 'in_the_wild' ||
    (item.references ?? []).some(
      (reference) =>
        reference.kev_added !== null ||
        reference.bdu_in_attacks ||
        reference.nvd_exploitation === 'active',
    )
  )
}

function hasPublicExploit(item: DigestItem): boolean {
  return (
    item.vulnerability?.exploit === 'public' ||
    (item.references ?? []).some(
      (reference) => reference.exploits.length > 0 || reference.nvd_exploitation === 'poc',
    )
  )
}

/**
 * How dangerous the flaw is: critical when exploited or scored 9 and up,
 * high with a public exploit or a score of 7 and up, otherwise moderate.
 */
export function severityBand(item: DigestItem): Band {
  const cvss = cvssOf(item)
  if (isExploited(item) || (cvss !== null && cvss >= 9)) return 2
  if (hasPublicExploit(item) || (cvss !== null && cvss >= 7)) return 1
  return 0
}

// The relevance of an entry to the profile's interests that counts as close.
const CLOSE = 0.8

/**
 * How close it is to the reader: it names their own systems, it matches the
 * profile's interests closely, or it is in the issue for a looser reason.
 */
export function exposureBand(item: DigestItem): Band {
  if ((item.ours ?? []).length > 0) return 2
  return item.score >= CLOSE ? 1 : 0
}

export type Placed = { position: number; item: DigestItem }

/** The vulnerabilities of an issue in the cells of a 3×3 matrix, [exposure][severity]. */
export function riskCells(entries: Placed[]): Placed[][][] {
  const cells: Placed[][][] = [0, 1, 2].map(() => [[], [], []])
  for (const entry of entries) {
    if (entry.item.kind !== 'vulnerability') continue
    cells[exposureBand(entry.item)][severityBand(entry.item)].push(entry)
  }
  return cells
}

export type TimelineEvent = {
  date: string
  label: string
  tone: 'neutral' | 'warning' | 'danger' | 'accent'
}

/**
 * The vulnerability's life as the bases date it, oldest first: published in
 * NVD, a public exploit, entered into CISA KEV, CISA's deadline, and the news.
 * Nothing before two dated events: one point is not a line.
 */
export function timelineOf(item: DigestItem): TimelineEvent[] {
  const reference = (item.references ?? []).find(
    (candidate) => candidate.nvd_published || candidate.exploit_published || candidate.kev_added,
  )
  if (!reference) return []
  const events: (TimelineEvent | null)[] = [
    reference.nvd_published
      ? { date: reference.nvd_published, label: 'Опубликована в NVD', tone: 'neutral' }
      : null,
    reference.exploit_published
      ? { date: reference.exploit_published, label: 'Публичный эксплойт', tone: 'warning' }
      : null,
    reference.kev_added
      ? { date: reference.kev_added, label: 'В каталоге CISA KEV', tone: 'danger' }
      : null,
    reference.kev_due ? { date: reference.kev_due, label: 'Срок CISA', tone: 'danger' } : null,
    { date: item.published_at.slice(0, 10), label: 'Новость в выпуске', tone: 'accent' },
  ]
  const dated = events.filter((event): event is TimelineEvent => event !== null)
  if (dated.length < 2) return []
  return dated.sort((a, b) => a.date.localeCompare(b.date))
}
