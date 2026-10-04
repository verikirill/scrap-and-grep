import { ShieldCheck } from '../../components/icons'
import { Chip } from '../../components/ui'
import type { DigestItem, Priority } from '../../lib/api'
import { inSentence } from '../../lib/format'

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
 * and what the check against the article took out.
 */
export function EntryDetails({ item }: { item: DigestItem }) {
  const filled = item.fields.filter((field) => field.value !== NO_DATA)
  const missing = item.fields.filter((field) => field.value === NO_DATA)
  return (
    <>
      {filled.length > 0 && (
        <dl className="mt-2.5 grid grid-cols-1 gap-x-3 gap-y-1 rounded-lg bg-surface-container px-3 py-2.5 text-[13px] sm:grid-cols-[auto_minmax(0,1fr)]">
          {filled.map((field) => (
            <div key={field.label} className="contents">
              <dt className="text-muted-foreground max-sm:mt-1.5 max-sm:text-xs">{field.label}</dt>
              <dd className="break-words text-foreground">{field.value}</dd>
            </div>
          ))}
          {missing.length > 0 && (
            <p className="text-xs text-outline sm:col-span-2 max-sm:mt-1.5">
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
        <div className="mt-2.5 text-xs text-muted-foreground">
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
          className="mt-2 flex items-start gap-1.5 text-xs text-outline"
          title="Число, идентификатор или название, которых нет в тексте статьи, в выпуск не попадают"
        >
          <ShieldCheck size={14} className="mt-px shrink-0" />
          Нет в тексте статьи, убрано проверкой: {item.unsupported.map(inSentence).join(', ')}
        </p>
      )}
    </>
  )
}
