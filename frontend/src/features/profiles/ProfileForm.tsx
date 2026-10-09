import { cn } from '../../lib/utils'
import clsx from 'clsx'
import { ChevronDown, Plus, Trash2 } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { ChipsInput } from '../../components/ChipsInput'
import { EASE, INPUT_CLASS, TEXTAREA_CLASS, shortId } from '../../components/tokens'
import { Button, Card, Chip, Field } from '../../components/ui'
import type { Audience, Interest, ProfileSpec, SourceCategory } from '../../lib/api'
import { CATEGORY_LABELS } from '../../lib/format'

const WEIGHT_LABELS: [number, string][] = [
  [0.75, 'второстепенный'],
  [1.15, 'обычный'],
  [Infinity, 'приоритетный'],
]

const weightLabel = (weight: number) => WEIGHT_LABELS.find(([limit]) => weight < limit)?.[1] ?? ''

/** Filled part of a range track, as a CSS variable read by index.css. */
const fill = (value: number, min: number, max: number) =>
  ({ '--fill': `${((value - min) / (max - min)) * 100}%` }) as CSSProperties

function InterestEditor({
  interest,
  isOpen,
  onToggle,
  onChange,
  onRemove,
  isRemovable,
}: {
  interest: Interest
  isOpen: boolean
  onToggle: () => void
  onChange: (next: Interest) => void
  onRemove: () => void
  isRemovable: boolean
}) {
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.25, ease: EASE }}
      className="rounded-xl border border-separator bg-surface"
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={`interest-panel-${interest.id}`}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className="min-w-0 flex-1">
          {/* Two lines, not one: next to the weight chip a phone left "Безопасность АСУ ТП и ...". */}
          <span className="line-clamp-2 text-sm font-medium break-words">
            {interest.title || 'Новый интерес'}
          </span>
          {!isOpen && (
            <span className="mt-0.5 block truncate text-xs text-muted">
              {interest.keywords.length > 0
                ? interest.keywords.slice(0, 6).join(', ')
                : 'ключевые слова не заданы'}
            </span>
          )}
        </span>
        {interest.weight !== 1 && (
          <Chip tone={interest.weight > 1 ? 'spark' : 'neutral'}>
            {weightLabel(interest.weight)}
          </Chip>
        )}
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={17} className="text-muted" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: EASE }}
            className="overflow-hidden"
            id={`interest-panel-${interest.id}`}
          >
            <div className="space-y-3.5 border-t border-separator px-4 py-4">
              <Field label="Название">
                <input
                  className={INPUT_CLASS}
                  value={interest.title}
                  maxLength={120}
                  onChange={(event) => onChange({ ...interest, title: event.target.value })}
                />
              </Field>
              <Field
                label="Что именно интересует"
                hint="по этому описанию строится смысловой поиск"
              >
                <textarea
                  className={cn(TEXTAREA_CLASS, 'min-h-16')}
                  value={interest.description}
                  maxLength={600}
                  onChange={(event) => onChange({ ...interest, description: event.target.value })}
                />
              </Field>
              <Field isGroup label="Ключевые слова" hint="Enter или запятая">
                <ChipsInput
                  label="Ключевые слова"
                  values={interest.keywords}
                  onChange={(keywords) => onChange({ ...interest, keywords })}
                  placeholder="SCADA, АСУ ТП, МЭК 61850"
                />
              </Field>
              <div className="flex items-end gap-4">
                <Field label="Важность" hint={weightLabel(interest.weight)} className="flex-1">
                  <input
                    type="range"
                    min={0.5}
                    max={1.5}
                    step={0.1}
                    value={interest.weight}
                    style={fill(interest.weight, 0.5, 1.5)}
                    onChange={(event) =>
                      onChange({
                        ...interest,
                        weight: Number(event.target.value),
                      })
                    }
                    className="w-full"
                  />
                </Field>
                <Button
                  size="sm"
                  variant="danger"
                  icon={<Trash2 size={14} />}
                  onClick={onRemove}
                  disabled={!isRemovable}
                >
                  Удалить
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

const CATEGORIES = Object.keys(CATEGORY_LABELS) as SourceCategory[]

// The two kinds of digest in the organizers' dataset.
const AUDIENCES: { id: Audience; title: string; description: string }[] = [
  {
    id: 'specialist',
    title: 'Специалисту',
    description: 'Карточки атак и уязвимостей с приоритетом, остальные новости — по темам',
  },
  {
    id: 'management',
    title: 'Руководству',
    description: 'Кратко и без терминов. С ключевыми метками: в РФ, ущерб, утечка, энергетика',
  },
]

export function ProfileForm({
  spec,
  onChange,
  look,
}: {
  spec: ProfileSpec
  onChange: (next: ProfileSpec) => void
  /** The icon and colour picker, beside the name; a new profile has none yet. */
  look?: ReactNode
}) {
  const [openId, setOpenId] = useState<string | null>(null)

  const updateInterest = (next: Interest) =>
    onChange({
      ...spec,
      interests: spec.interests.map((interest) => (interest.id === next.id ? next : interest)),
    })

  const addInterest = () => {
    const id = `interest-${shortId()}`
    onChange({
      ...spec,
      interests: [...spec.interests, { id, title: '', description: '', keywords: [], weight: 1 }],
    })
    setOpenId(id)
  }

  const toggleCategory = (category: SourceCategory) => {
    const active = spec.categories.includes(category)
    onChange({
      ...spec,
      categories: active
        ? spec.categories.filter((item) => item !== category)
        : [...spec.categories, category],
    })
  }

  return (
    <div className="space-y-5">
      <Card className="space-y-4 p-5">
        <div className="flex items-end gap-3">
          {look}
          <Field label="Название профиля" className="min-w-0 flex-1">
            <input
              className={INPUT_CLASS}
              value={spec.name}
              maxLength={120}
              onChange={(event) => onChange({ ...spec, name: event.target.value })}
            />
          </Field>
        </div>
        <Field label="Роль читателя" hint="по этому описанию модель формулирует «почему важно»">
          <textarea
            className={TEXTAREA_CLASS}
            value={spec.role}
            maxLength={600}
            onChange={(event) => onChange({ ...spec, role: event.target.value })}
          />
        </Field>
        <Field isGroup label="Формат выпуска" hint="как в датасете организаторов">
          <div role="radiogroup" aria-label="Формат выпуска" className="grid gap-2 sm:grid-cols-2">
            {AUDIENCES.map((option) => {
              const active = spec.audience === option.id
              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => onChange({ ...spec, audience: option.id })}
                  className={clsx(
                    'rounded-xl border px-3.5 py-2.5 text-left transition-colors duration-150',
                    active
                      ? 'border-accent bg-accent-soft text-accent-soft-foreground'
                      : 'border-separator hover:border-border',
                  )}
                >
                  <span className="block text-sm font-medium">{option.title}</span>
                  <span
                    className={clsx(
                      'mt-0.5 block text-xs',
                      active ? 'text-accent-soft-foreground/80' : 'text-muted',
                    )}
                  >
                    {option.description}
                  </span>
                </button>
              )
            })}
          </div>
        </Field>
      </Card>

      <div>
        <div className="mb-2.5 flex items-center justify-between px-1">
          <h2 className="text-sm font-semibold">Интересы</h2>
          <Button
            size="sm"
            variant="ghost"
            icon={<Plus size={15} />}
            onClick={addInterest}
            disabled={spec.interests.length >= 20}
          >
            Добавить
          </Button>
        </div>
        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {spec.interests.map((interest) => (
              <InterestEditor
                key={interest.id}
                interest={interest}
                isOpen={openId === interest.id}
                onToggle={() => setOpenId(openId === interest.id ? null : interest.id)}
                onChange={updateInterest}
                isRemovable={spec.interests.length > 1}
                onRemove={() =>
                  onChange({
                    ...spec,
                    interests: spec.interests.filter((item) => item.id !== interest.id),
                  })
                }
              />
            ))}
          </AnimatePresence>
        </div>
      </div>

      <Card className="space-y-5 p-5">
        <Field isGroup label="Не показывать" hint="темы, которых не должно быть в выпуске">
          <ChipsInput
            label="Исключения"
            values={spec.exclusions}
            onChange={(exclusions) => onChange({ ...spec, exclusions })}
            placeholder="вакансии, обзоры гаджетов"
            max={20}
          />
        </Field>

        <Field
          isGroup
          label="Наши системы"
          hint="производители и продукты, например Cisco ASA, Siemens S7-1500, 1С"
        >
          <ChipsInput
            label="Наши системы"
            values={spec.systems ?? []}
            onChange={(systems) => onChange({ ...spec, systems })}
            placeholder="Cisco ASA, Siemens S7-1500"
            max={40}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Порог релевантности" hint={spec.min_score.toFixed(2)}>
            <input
              type="range"
              min={0.2}
              max={0.9}
              step={0.05}
              value={spec.min_score}
              style={fill(spec.min_score, 0.2, 0.9)}
              onChange={(event) => onChange({ ...spec, min_score: Number(event.target.value) })}
              className="w-full"
            />
          </Field>
          <Field label="Размер выпуска" hint={`до ${spec.max_items} публикаций`}>
            <input
              type="range"
              min={5}
              max={40}
              step={1}
              value={spec.max_items}
              style={fill(spec.max_items, 5, 40)}
              onChange={(event) => onChange({ ...spec, max_items: Number(event.target.value) })}
              className="w-full"
            />
          </Field>
        </div>

        <div>
          <p className="mb-2 flex items-baseline justify-between text-[13px] font-medium">
            Источники
            <span className="text-xs font-normal text-muted">
              {spec.categories.length === 0 ? 'все категории' : 'только выбранные'}
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map((category) => {
              const active = spec.categories.includes(category)
              return (
                <button
                  key={category}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleCategory(category)}
                  className={clsx(
                    'rounded-lg border px-2.5 py-1 text-[13px] transition-colors duration-150',
                    active
                      ? 'border-accent bg-accent-soft text-accent-soft-foreground'
                      : 'border-separator text-muted hover:border-border hover:text-foreground',
                  )}
                >
                  {CATEGORY_LABELS[category]}
                </button>
              )
            })}
          </div>
        </div>
      </Card>
    </div>
  )
}
