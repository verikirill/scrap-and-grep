import { cn } from '../../lib/utils'
import clsx from 'clsx'
import { Check } from '../../components/icons'
import { motion } from 'motion/react'
import { INPUT_CLASS, rowMotion } from '../../components/tokens'
import { Field } from '../../components/ui'
import type { Interest, ProfileSpec } from '../../lib/api'

type Props = {
  spec: ProfileSpec
  /** Ids of the suggested interests the reader keeps. */
  kept: string[]
  onSpecChange: (next: ProfileSpec) => void
  onKeptChange: (next: string[]) => void
}

function InterestOption({
  interest,
  index,
  isKept,
  onToggle,
}: {
  interest: Interest
  index: number
  isKept: boolean
  onToggle: () => void
}) {
  return (
    <motion.li {...rowMotion(index)}>
      <button
        type="button"
        role="checkbox"
        aria-checked={isKept}
        onClick={onToggle}
        className={clsx(
          'flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors duration-150',
          isKept
            ? 'border-primary/50 bg-primary-container/50'
            : 'border-outline-variant bg-card hover:border-outline',
        )}
      >
        <span
          className={clsx(
            'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border transition-colors duration-150',
            isKept
              ? 'border-primary bg-primary text-white dark:text-[#0b0f17]'
              : 'border-outline-variant',
          )}
        >
          {isKept && <Check size={13} strokeWidth={3} />}
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-medium">{interest.title}</span>
          {interest.description && (
            <span className="mt-0.5 block text-[13px] text-muted-foreground">
              {interest.description}
            </span>
          )}
          <span className="mt-1.5 block text-xs text-outline">
            {interest.keywords.slice(0, 8).join(' · ')}
          </span>
        </span>
      </button>
    </motion.li>
  )
}

/**
 * The profile suggested from a resume, before it is saved. The reader picks
 * the topics and may reword who they are; fine tuning waits in "Интересы".
 */
export function SuggestionEditor({ spec, kept, onSpecChange, onKeptChange }: Props) {
  const toggle = (id: string) =>
    onKeptChange(kept.includes(id) ? kept.filter((item) => item !== id) : [...kept, id])

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название профиля">
          <input
            className={INPUT_CLASS}
            value={spec.name}
            maxLength={120}
            onChange={(event) => onSpecChange({ ...spec, name: event.target.value })}
          />
        </Field>
        <Field label="Размер выпуска" hint={`до ${spec.max_items} публикаций`}>
          <input
            type="range"
            min={5}
            max={40}
            value={spec.max_items}
            style={{
              ['--fill' as string]: `${((spec.max_items - 5) / 35) * 100}%`,
            }}
            onChange={(event) => onSpecChange({ ...spec, max_items: Number(event.target.value) })}
            className="mt-3 w-full"
          />
        </Field>
      </div>
      <Field label="Кто читатель" hint="по этому тексту модель пишет «почему важно»">
        <textarea
          className={cn(INPUT_CLASS, 'min-h-20 resize-y')}
          value={spec.role}
          maxLength={600}
          onChange={(event) => onSpecChange({ ...spec, role: event.target.value })}
        />
      </Field>
      <div role="group" aria-label="Темы новостей">
        <p className="mb-2 flex items-baseline justify-between">
          <span className="text-[13px] font-medium">Темы новостей</span>
          <span className="text-xs text-outline">
            выбрано {kept.length} из {spec.interests.length}
          </span>
        </p>
        <ul className="space-y-2">
          {spec.interests.map((interest, index) => (
            <InterestOption
              key={interest.id}
              interest={interest}
              index={index}
              isKept={kept.includes(interest.id)}
              onToggle={() => toggle(interest.id)}
            />
          ))}
        </ul>
      </div>
    </div>
  )
}
