import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { FileText, Layers, PenLine } from '../../components/icons'
import { Button, Card } from '../../components/ui'
import { useRadioKeys } from '../../components/useRadioKeys'
import type { Profile } from '../../lib/api'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { ResumeFlow } from '../resume/ResumeFlow'
import { ChoiceCard } from './ChoiceCard'
import { StepHeading } from './StepHeading'
import { TemplatePicker } from './TemplatePicker'
import { REVEAL } from './motion'

const METHODS = [
  {
    key: 'resume',
    icon: FileText,
    title: 'По резюме',
    text: 'Загрузите файл, и сервис сам предложит темы под вашу работу.',
  },
  {
    key: 'template',
    icon: Layers,
    title: 'Готовый шаблон',
    text: 'Профиль для типичной роли в энергетике, ИТ или ИБ.',
  },
  {
    key: 'manual',
    icon: PenLine,
    title: 'Вручную',
    text: 'Темы, ключевые слова и исключения задаёте сами.',
  },
] as const
type Method = (typeof METHODS)[number]['key']

type Props = {
  profiles: Profile[]
  onProfile: (profile: Profile) => void
  onManual: () => void
  isLeaving: boolean
}

/** The working step: a profile from the resume, from a template, or by hand. */
export function ProfileStep({ profiles, onProfile, onManual, isLeaving }: Props) {
  const [method, setMethod] = useState<Method | null>(null)
  const chosen = METHODS.findIndex((item) => item.key === method)
  const keys = useRadioKeys(METHODS.length, chosen, (index) => setMethod(METHODS[index].key))
  const existing = profiles[0]

  return (
    <>
      <StepHeading kicker="Настройка">Первый профиль интересов</StepHeading>
      <p className="mt-2 mb-6 max-w-xl text-sm text-muted">
        Профиль подсказывает сервису, какие темы важны в вашей работе. Потом его можно поправить в
        разделе «Интересы».
      </p>

      {existing && (
        <Card variant="filled" className="mb-5 flex flex-wrap items-center gap-3 p-4">
          <ProfileAvatar profile={existing} size={36} />
          <p className="min-w-0 flex-1 text-sm">У вас уже есть профиль «{existing.spec.name}».</p>
          <Button size="sm" variant="tonal" onClick={() => onProfile(existing)}>
            Продолжить с ним
          </Button>
        </Card>
      )}

      <div
        role="radiogroup"
        aria-label="Как создать профиль"
        onKeyDown={keys.onKeyDown}
        className="grid gap-2 sm:grid-cols-3"
      >
        {METHODS.map((item, index) => (
          <ChoiceCard
            key={item.key}
            {...keys.itemProps(index)}
            isChosen={item.key === method}
            onChoose={() => setMethod(item.key)}
            leading={
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-soft-foreground">
                <item.icon size={18} />
              </span>
            }
            title={item.title}
          >
            {item.text}
          </ChoiceCard>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {method && (
          <motion.div key={method} {...REVEAL} className="mt-6">
            {method === 'resume' && <ResumeFlow saveLabel="Создать профиль" onSaved={onProfile} />}
            {method === 'template' && <TemplatePicker onCreated={onProfile} />}
            {method === 'manual' && (
              <Card variant="filled" className="p-5 sm:p-6">
                <p className="text-sm text-muted">
                  В редакторе сразу видно, какие публикации попадут в выпуск. Когда профиль будет
                  готов, нажмите там «Собрать выпуск».
                </p>
                <Button variant="primary" className="mt-4" isBusy={isLeaving} onClick={onManual}>
                  Открыть редактор
                </Button>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
