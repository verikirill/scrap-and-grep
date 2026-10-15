import { ShieldCheck } from '../../components/icons'
import { Chip } from '../../components/ui'
import type { DigestItem, Priority } from '../../lib/api'
import { inSentence } from '../../lib/format'
import { verifiedBases } from '../../lib/risk'

const PRIORITY_LABELS: Record<Priority, string> = {
  high: 'Высокий приоритет',
  medium: 'Средний приоритет',
  low: 'Низкий приоритет',
}
const PRIORITY_TONES = { high: 'alarm', medium: 'spark', low: 'neutral' } as const
const NO_DATA = 'нет данных'

/** The priority the organizers' dataset gives an attack or a vulnerability. */
export function PriorityChip({ item }: { item: DigestItem }) {
  if (!item.priority) return null
  return (
    <Chip tone={PRIORITY_TONES[item.priority]} title={item.priority_reason}>
      {PRIORITY_LABELS[item.priority]}
    </Chip>
  )
}

/** "Сверено", as the "verified" mark of a profile: a small green stamp with a shield. */
export function VerifiedBadge({ item }: { item: DigestItem }) {
  const bases = verifiedBases(item)
  if (bases.length === 0) return null
  return (
    <span
      title={`Идентификаторы сверены с ${bases.join(' и ')}`}
      className="inline-flex items-center gap-1 rounded-md bg-success-soft px-1.5 py-0.5 text-[10px] leading-4 font-bold tracking-[0.08em] text-success-soft-foreground uppercase"
    >
      <ShieldCheck size={12} aria-hidden />
      Сверено
    </span>
  )
}

/** "https://github[.]com/x": readable, not clickable. A post may point at a working exploit. */
function defang(url: string): string {
  try {
    const parsed = new URL(url)
    return url.replace(parsed.host, parsed.host.replaceAll('.', '[.]'))
  } catch {
    return url
  }
}

/**
 * The dataset's card: the fields the article fills, then in one line the
 * ones it is silent about. Tags for management, cited links of a channel post,
 * and what the check against the article took out. The rows the reader's
 * profile hides are left out here too, should the page hold them.
 */
export function EntryDetails({ item }: { item: DigestItem }) {
  const hidden = new Set<string>(item.hidden_fields ?? [])
  // Indicators and techniques have their own block (ThreatIntel): not twice.
  const ownBlock = new Set([
    ...(item.attack?.indicators.length ? ['Индикаторы компрометации'] : []),
    ...(item.attack?.techniques.length ? ['Техники ATT&CK'] : []),
  ])
  const fields = item.fields.filter((field) => !ownBlock.has(field.label) && !hidden.has(field.key))
  const filled = fields.filter((field) => field.value !== NO_DATA)
  const missing = fields.filter((field) => field.value === NO_DATA)
  return (
    <>
      {filled.length > 0 && (
        <dl className="mt-2.5 grid grid-cols-1 gap-x-3 gap-y-1 rounded-lg bg-surface-secondary px-3 py-2.5 text-[13px] sm:grid-cols-[auto_minmax(0,1fr)]">
          {filled.map((field) => (
            <div key={field.label} className="contents">
              <dt className="text-muted max-sm:mt-1.5 max-sm:text-xs">{field.label}</dt>
              <dd className="break-words text-foreground">{field.value}</dd>
            </div>
          ))}
          {missing.length > 0 && (
            <p className="text-xs text-muted sm:col-span-2 max-sm:mt-1.5">
              Нет в тексте: {missing.map((field) => inSentence(field.label)).join(', ')}
            </p>
          )}
        </dl>
      )}
      {item.tag_labels.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {item.tag_labels.map((label) => (
            <Chip key={label}>{label}</Chip>
          ))}
        </div>
      )}
      {item.links.length > 0 && (
        <div className="mt-2.5 text-xs text-muted">
          Ссылки из поста:
          <ul className="mt-1 space-y-0.5">
            {item.links.map((url) => (
              <li key={url} className="font-mono break-all text-foreground/80">
                {defang(url)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {item.unsupported.length > 0 && (
        <p
          className="mt-2 flex items-start gap-1.5 text-xs text-muted"
          title="Число, идентификатор или название, которых нет в тексте статьи, в выпуск не попадают"
        >
          <ShieldCheck size={14} className="mt-px shrink-0" />
          Нет в тексте статьи, убрано проверкой: {item.unsupported.map(inSentence).join(', ')}
        </p>
      )}
    </>
  )
}
