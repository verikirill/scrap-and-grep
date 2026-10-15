import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { ChipsInput } from '../../components/ChipsInput'
import { Plus, X } from '../../components/icons'
import { Segmented } from '../../components/Segmented'
import { EASE, INPUT_CLASS, TEXTAREA_CLASS } from '../../components/tokens'
import { Button, Card, Field } from '../../components/ui'
import type { Audience, ProfileSpec } from '../../lib/api'
import { plural } from '../../lib/format'

const AUDIENCES: { value: Audience; label: string }[] = [
  { value: 'specialist', label: 'Карточки специалиста' },
  { value: 'management', label: 'Брифинг руководителя' },
]

let added = 0
const newId = () => `added-local-${Date.now().toString(36)}-${(added += 1)}`

/** A topic the manager writes in: a title and the words its news carry. */
export function AddTopic({ onAdd }: { onAdd: (title: string, keywords: string[]) => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [keywords, setKeywords] = useState<string[]>([])
  if (!isOpen) {
    return (
      <Button size="sm" variant="ghost" icon={<Plus size={15} />} onClick={() => setIsOpen(true)}>
        Добавить тему
      </Button>
    )
  }
  return (
    <div className="space-y-3 rounded-2xl bg-surface p-3">
      <Field label="Тема">
        <input
          autoFocus
          maxLength={120}
          placeholder="Облачные сервисы"
          className={INPUT_CLASS}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </Field>
      <Field label="Ключевые слова" hint="Enter или запятая добавляют" isGroup>
        <ChipsInput
          label="Ключевые слова"
          placeholder="SaaS, облако, Yandex Cloud…"
          values={keywords}
          onChange={setKeywords}
          max={20}
        />
      </Field>
      <div className="flex justify-end gap-2">
        <Button size="sm" onClick={() => setIsOpen(false)}>
          Отмена
        </Button>
        <Button
          size="sm"
          variant="primary"
          disabled={title.trim().length < 2}
          onClick={() => {
            onAdd(title.trim(), keywords)
            setTitle('')
            setKeywords([])
            setIsOpen(false)
          }}
        >
          Добавить
        </Button>
      </div>
    </div>
  )
}

type Props = {
  spec: ProfileSpec
  onChange: (spec: ProfileSpec) => void
  title: string
  /** Who made the draft: the model's name, or "taxonomy"; null for a stored profile. */
  draftedBy?: string | null
  /** Whether the format of a digest is chosen here, as for a role. */
  withAudience?: boolean
}

/**
 * The profile the service proposed, for the manager to check: the role in
 * words, the topics (any can go, new ones can come in) and, for a role, the
 * format of its digests.
 */
export function SpecReview({
  spec,
  onChange,
  title,
  draftedBy = null,
  withAudience = false,
}: Props) {
  const drop = (id: string) =>
    onChange({ ...spec, interests: spec.interests.filter((item) => item.id !== id) })
  const add = (topic: string, keywords: string[]) =>
    onChange({
      ...spec,
      interests: [
        ...spec.interests,
        { id: newId(), title: topic, description: '', keywords, weight: 1 },
      ],
    })

  return (
    <Card variant="filled" className="space-y-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {draftedBy && (
          <span className="text-xs text-muted">
            {draftedBy === 'taxonomy'
              ? 'Подобран по справочнику направлений'
              : 'Подобран моделью по описанию'}
          </span>
        )}
      </div>
      <Field label="Роль" hint="сотрудник увидит её в начале своего профиля">
        <textarea
          maxLength={600}
          rows={3}
          className={TEXTAREA_CLASS}
          value={spec.role}
          onChange={(event) => onChange({ ...spec, role: event.target.value })}
        />
      </Field>
      {withAudience && (
        <Field label="Формат выпусков" isGroup>
          <Segmented
            label="Формат выпусков"
            value={spec.audience}
            options={AUDIENCES}
            onChange={(audience) => onChange({ ...spec, audience })}
          />
        </Field>
      )}
      <div>
        <p className="mb-1.5 px-1 text-[13px] font-medium text-muted">
          {spec.interests.length} {plural(spec.interests.length, ['тема', 'темы', 'тем'])} новостей
        </p>
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {spec.interests.map((interest) => (
              <motion.li
                key={interest.id}
                layout
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2, ease: EASE }}
                className="flex items-start gap-3 rounded-2xl bg-surface p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium break-words">{interest.title}</p>
                  {interest.description && (
                    <p className="mt-0.5 text-xs text-muted">{interest.description}</p>
                  )}
                  {interest.keywords.length > 0 && (
                    <p className="mt-1 text-xs break-words text-muted">
                      {interest.keywords.slice(0, 8).join(' · ')}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  aria-label={`Убрать тему «${interest.title}»`}
                  disabled={spec.interests.length === 1}
                  onClick={() => drop(interest.id)}
                  className="button button--ghost button--icon-only button--sm shrink-0 text-muted"
                >
                  <X size={15} />
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        {spec.interests.length < 20 && (
          <div className="mt-2">
            <AddTopic onAdd={add} />
          </div>
        )}
      </div>
    </Card>
  )
}
