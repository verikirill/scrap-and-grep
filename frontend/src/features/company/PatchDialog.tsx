import { useState } from 'react'
import { ChipsInput } from '../../components/ChipsInput'
import { X } from '../../components/icons'
import { Segmented } from '../../components/Segmented'
import { SelectField } from '../../components/SelectField'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { Audience, Interest } from '../../lib/api'
import type { PatchTarget, ProfilePatch, Team } from '../../lib/company'
import { usePatchProfiles } from '../../lib/companyQueries'
import { plural } from '../../lib/format'
import { toast } from '../../lib/toast'
import { cn } from '../../lib/utils'
import { AddTopic } from './SpecReview'

type Scope = PatchTarget['scope']
type Keep = 'keep'

const FORMATS: { value: Audience | Keep; label: string }[] = [
  { value: 'keep', label: 'Не менять' },
  { value: 'specialist', label: 'Карточки' },
  { value: 'management', label: 'Брифинг' },
]
const SIZES = [
  { value: '', label: 'Не менять' },
  ...[8, 10, 15, 20, 30].map((size) => ({ value: String(size), label: `${size} новостей` })),
]
const people = (count: number) => plural(count, ['сотрудник', 'сотрудника', 'сотрудников'])

type Props = {
  team: Team
  /** The people chosen in the list; the dialog offers them as a target. */
  selected: string[]
  /** Where the dialog opens: a role's button opens it on that role. */
  initial: PatchTarget
  onClose: () => void
}

/** The topics a target reads now, for the manager to take some out. */
function topicsOf(team: Team, scope: Scope, roleId: string, selected: string[]): Interest[] {
  const roleSpecs = (ids: Set<string | null>) =>
    team.roles.filter((role) => ids.has(role.id)).map((role) => role.spec)
  const chosen = new Set(
    team.members.filter((member) => selected.includes(member.id)).map((member) => member.role_id),
  )
  const specs =
    scope === 'role'
      ? roleSpecs(new Set([roleId]))
      : scope === 'people'
        ? [...(chosen.has(null) ? [team.spec] : []), ...roleSpecs(chosen)]
        : [team.spec, ...team.roles.map((role) => role.spec)]
  // One chip per title, as the server matches topics by title.
  const seen = new Map<string, Interest>()
  for (const interest of specs.flatMap((spec) => spec.interests)) {
    const key = interest.title.toLocaleLowerCase('ru')
    if (!seen.has(key)) seen.set(key, interest)
  }
  return [...seen.values()]
}

/**
 * One change for many profiles at once: the whole team, everyone with a role,
 * or the people chosen in the list. Topics in or out, exclusions, products,
 * the format and the size of a digest; whatever is left alone stays.
 */
export function PatchDialog({ team, selected, initial, onClose }: Props) {
  const patch = usePatchProfiles()
  const [scope, setScope] = useState<Scope>(initial.scope)
  const [roleId, setRoleId] = useState(
    initial.scope === 'role' ? initial.role_id : (team.roles[0]?.id ?? ''),
  )
  const [added, setAdded] = useState<{ title: string; keywords: string[] }[]>([])
  const [removed, setRemoved] = useState<string[]>([])
  const [exclusions, setExclusions] = useState<string[]>([])
  const [systems, setSystems] = useState<string[]>([])
  const [format, setFormat] = useState<Audience | Keep>('keep')
  const [size, setSize] = useState('')

  const scopes = [
    { value: 'team' as const, label: 'Вся команда' },
    ...(team.roles.length ? [{ value: 'role' as const, label: 'Роль' }] : []),
    ...(selected.length
      ? [{ value: 'people' as const, label: `Выбранные: ${selected.length}` }]
      : []),
  ]
  const reach =
    scope === 'team'
      ? team.members.length
      : scope === 'role'
        ? team.members.filter((member) => member.role_id === roleId).length
        : selected.length
  const topics = topicsOf(team, scope, roleId, selected)
  const change: ProfilePatch = {
    ...(added.length && { add_interests: added }),
    ...(removed.length && { remove_interests: removed }),
    ...(exclusions.length && { add_exclusions: exclusions }),
    ...(systems.length && { add_systems: systems }),
    ...(format !== 'keep' && { audience: format }),
    ...(size && { max_items: Number(size) }),
  }
  const isEmpty = Object.keys(change).length === 0
  const target: PatchTarget =
    scope === 'role'
      ? { scope, role_id: roleId }
      : scope === 'people'
        ? { scope, member_ids: selected }
        : { scope }

  const toggle = (title: string) =>
    setRemoved((current) =>
      current.includes(title) ? current.filter((item) => item !== title) : [...current, title],
    )

  return (
    <Dialog open onOpenChange={(open) => !open && !patch.isPending && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Изменить профили</DialogTitle>
          <DialogDescription>
            Правка дойдёт до всех, кого вы выберете. Остальное в профилях останется как было.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="space-y-2">
            <Segmented label="Кому" value={scope} options={scopes} onChange={setScope} />
            {scope === 'role' && (
              <SelectField
                label="Роль"
                value={roleId}
                onChange={setRoleId}
                options={team.roles.map((role) => ({ value: role.id, label: role.name }))}
              />
            )}
            <p className="px-1 text-xs text-muted">
              {scope === 'people'
                ? 'Правка закрепится за этими людьми и сохранится, когда команда изменится.'
                : scope === 'role'
                  ? 'Правка войдёт в профиль роли.'
                  : 'Правка войдёт в профиль команды и всех её ролей.'}{' '}
              Получат {reach} {people(reach)}.
            </p>
          </div>

          {topics.length > 0 && (
            <Field label="Убрать темы" hint="нажмите на тему" isGroup>
              <div className="flex flex-wrap gap-1.5">
                {topics.map((topic) => {
                  const isOff = removed.includes(topic.title)
                  return (
                    <button
                      key={topic.id}
                      type="button"
                      aria-pressed={isOff}
                      onClick={() => toggle(topic.title)}
                      className={cn(
                        'chip gap-1 px-2.5 py-1 transition-colors',
                        isOff
                          ? 'chip--danger chip--soft line-through'
                          : 'chip--accent chip--soft hover:opacity-80',
                      )}
                    >
                      {topic.title}
                      {isOff && <X size={13} aria-hidden />}
                    </button>
                  )
                })}
              </div>
            </Field>
          )}

          <Field label="Добавить темы" isGroup>
            {added.length > 0 && (
              <ul className="mb-2 flex flex-wrap gap-1.5">
                {added.map((topic) => (
                  <li key={topic.title} className="chip chip--success chip--soft gap-1 px-2.5 py-1">
                    {topic.title}
                    <button
                      type="button"
                      aria-label={`Не добавлять «${topic.title}»`}
                      onClick={() => setAdded(added.filter((item) => item !== topic))}
                      className="-mr-1 rounded-full opacity-70 hover:opacity-100"
                    >
                      <X size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <AddTopic
              onAdd={(title, keywords) =>
                setAdded((current) =>
                  current.some((item) => item.title === title)
                    ? current
                    : [...current, { title, keywords }],
                )
              }
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Исключить из выдачи" isGroup>
              <ChipsInput
                label="Исключить из выдачи"
                placeholder="реклама, вакансии…"
                values={exclusions}
                onChange={setExclusions}
                max={20}
              />
            </Field>
            <Field label="Добавить продукты" isGroup>
              <ChipsInput
                label="Добавить продукты"
                placeholder="Cisco ASA, 1С…"
                values={systems}
                onChange={setSystems}
                max={20}
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Формат выпусков" isGroup>
              <Segmented
                label="Формат выпусков"
                value={format}
                options={FORMATS}
                onChange={setFormat}
              />
            </Field>
            <Field label="Размер выпуска" isGroup>
              <SelectField label="Размер выпуска" value={size} onChange={setSize} options={SIZES} />
            </Field>
          </div>

          <ErrorNote error={patch.error} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button disabled={patch.isPending} onClick={onClose}>
              Отмена
            </Button>
            <Button
              variant="primary"
              isBusy={patch.isPending}
              disabled={isEmpty || reach === 0 || (scope === 'role' && !roleId)}
              onClick={() =>
                patch.mutate(
                  { teamId: team.id, target, patch: change },
                  {
                    onSuccess: ({ changed }) => {
                      toast.success(`Профили обновлены: ${changed}`)
                      onClose()
                    },
                  },
                )
              }
            >
              Применить
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
