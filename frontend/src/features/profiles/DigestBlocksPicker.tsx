import type { Audience } from '../../lib/api'
import { blocksFor, withHiddenBlock } from '../../lib/digestBlocks'
import type { DigestBlockKey } from '../../lib/digestBlocks'
import { plural } from '../../lib/format'
import { FoldedPicker, ShowChip } from './FoldedPicker'

/** "все показаны" or "скрыто 2 блока", counting only this format's blocks. */
function shownSummary(hidden: number): string {
  if (hidden === 0) return 'все показаны'
  return `скрыто ${hidden} ${plural(hidden, ['блок', 'блока', 'блоков'])}`
}

/**
 * Which blocks around the entries the digest page shows, folded under one
 * line, with only the blocks the chosen format has. A ticked block is shown;
 * all are by default. A hidden block of the other format stays hidden if the
 * reader switches back to it.
 */
export function DigestBlocksPicker({
  audience,
  hidden,
  onChange,
}: {
  audience: Audience
  hidden: readonly DigestBlockKey[]
  onChange: (next: DigestBlockKey[]) => void
}) {
  const blocks = blocksFor(audience)
  const hiddenSet = new Set(hidden)
  const hiddenHere = blocks.filter((block) => hiddenSet.has(block.key)).length
  return (
    <FoldedPicker
      title="Блоки выпуска"
      summary={shownSummary(hiddenHere)}
      note="Снимите галочку, чтобы блок не показывался в выпуске. Если блок есть в файлах и письме, он пропадёт и оттуда. Записи, заголовок и «Главное» видны всегда."
    >
      <fieldset>
        <legend className="sr-only">Блоки выпуска</legend>
        <div className="flex flex-wrap gap-1.5">
          {blocks.map((block) => (
            <ShowChip
              key={block.key}
              label={block.label}
              isShown={!hiddenSet.has(block.key)}
              onChange={(isShown) => onChange(withHiddenBlock(hidden, block.key, !isShown))}
            />
          ))}
        </div>
      </fieldset>
    </FoldedPicker>
  )
}
