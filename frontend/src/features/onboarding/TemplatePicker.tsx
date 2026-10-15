import { useState } from 'react'
import { Loading, Skeleton } from '../../components/loading'
import { useRadioKeys } from '../../components/useRadioKeys'
import { Button, ErrorNote, ErrorState } from '../../components/ui'
import type { Profile } from '../../lib/api'
import { plural } from '../../lib/format'
import { useAddTemplate, useProfileTemplates } from '../../lib/queries'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { ChoiceCard } from './ChoiceCard'

/** Ready profiles for typical roles: one is picked and becomes the reader's own. */
export function TemplatePicker({ onCreated }: { onCreated: (profile: Profile) => void }) {
  const templates = useProfileTemplates()
  const add = useAddTemplate()
  const [chosen, setChosen] = useState(-1)
  const list = templates.data ?? []
  const keys = useRadioKeys(list.length, chosen, setChosen)

  if (templates.isPending) {
    return (
      <Loading label="Загружаем шаблоны" className="space-y-2">
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
      </Loading>
    )
  }
  if (templates.isError) {
    return (
      <ErrorState
        title="Шаблоны не загрузились"
        error={templates.error}
        action={<Button onClick={() => void templates.refetch()}>Повторить</Button>}
      />
    )
  }

  const template = list[chosen]
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Выберите роль, которая ближе всего к вашей. Темы и ключевые слова можно поменять позже.
      </p>
      <div
        role="radiogroup"
        aria-label="Шаблоны профилей"
        onKeyDown={keys.onKeyDown}
        className="grid gap-2"
      >
        {list.map((item, index) => (
          <ChoiceCard
            key={item.spec.name}
            {...keys.itemProps(index)}
            isChosen={index === chosen}
            onChoose={() => setChosen(index)}
            leading={<ProfileAvatar profile={item} size={36} />}
            title={item.spec.name}
          >
            {item.spec.interests.length}{' '}
            {plural(item.spec.interests.length, ['тема', 'темы', 'тем'])}:{' '}
            {item.spec.interests.map((interest) => interest.title).join(', ')}
          </ChoiceCard>
        ))}
      </div>
      <ErrorNote error={add.error} />
      <Button
        variant="cta"
        className="w-full sm:w-auto"
        disabled={!template}
        isBusy={add.isPending}
        onClick={() => template && add.mutate(template, { onSuccess: onCreated })}
      >
        Взять этот шаблон
      </Button>
    </div>
  )
}
