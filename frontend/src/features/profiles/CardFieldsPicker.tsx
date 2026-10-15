import { CARD_FIELD_GROUPS, withHidden } from '../../lib/cardFields'
import type { CardFieldKey } from '../../lib/cardFields'
import { plural } from '../../lib/format'
import { FoldedPicker, ShowChip } from './FoldedPicker'

/** "все показаны" or "скрыто 3 поля": the setting at a glance, while folded. */
function shownSummary(hidden: number): string {
  if (hidden === 0) return 'все показаны'
  return `скрыто ${hidden} ${plural(hidden, ['поле', 'поля', 'полей'])}`
}

/**
 * Which rows of the attack and vulnerability cards the reader sees, folded
 * under one line. A ticked row is shown; all are by default. The headline,
 * the summary, the priority and "Почему это важно" are not in the list: they
 * always stay.
 */
export function CardFieldsPicker({
  hidden,
  onChange,
}: {
  hidden: readonly CardFieldKey[]
  onChange: (next: CardFieldKey[]) => void
}) {
  const hiddenSet = new Set(hidden)
  return (
    <FoldedPicker
      title="Поля карточек"
      summary={shownSummary(hidden.length)}
      note="Снимите галочку, чтобы поле не показывалось в выпуске, файлах и письме. Заголовок, краткое содержание, приоритет и «Почему это важно» видны всегда."
    >
      {CARD_FIELD_GROUPS.map((group) => (
        <fieldset key={group.kind}>
          <legend className="mb-1.5 text-[13px] font-medium">{group.title}</legend>
          <div className="flex flex-wrap gap-1.5">
            {group.fields.map((field) => (
              <ShowChip
                key={field.key}
                label={field.label}
                isShown={!hiddenSet.has(field.key)}
                onChange={(isShown) => onChange(withHidden(hidden, field.key, !isShown))}
              />
            ))}
          </div>
        </fieldset>
      ))}
    </FoldedPicker>
  )
}
