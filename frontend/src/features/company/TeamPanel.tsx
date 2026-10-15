import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import {
  ContentCopy,
  PenLine,
  Plus,
  SlidersHorizontal,
  Trash2,
  UserPlus,
  Users,
  X,
} from '../../components/icons'
import { SelectField } from '../../components/SelectField'
import { EASE } from '../../components/tokens'
import { Button, Card, Chip, EmptyState, ErrorNote } from '../../components/ui'
import type { PatchTarget, Role, Team } from '../../lib/company'
import { useDeleteRole, useDeleteTeam, useMoveMembers } from '../../lib/companyQueries'
import { plural } from '../../lib/format'
import { toast } from '../../lib/toast'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { AddPeopleDialog } from './AddPeopleDialog'
import { copyText, invitationsText } from './copy'
import { MemberList } from './MemberList'
import { PatchDialog } from './PatchDialog'
import { RoleEditor } from './RoleEditor'

type Props = {
  team: Team
  teams: Team[]
  onEdit: () => void
  onDeleted: () => void
}

const people = (count: number) => plural(count, ['сотрудник', 'сотрудника', 'сотрудников'])

/** The roles of a team: who reads what within it, and how many people each has. */
function Roles({
  team,
  onEdit,
  onPatch,
}: {
  team: Team
  onEdit: (role: Role | null) => void
  onPatch: (role: Role) => void
}) {
  const remove = useDeleteRole()
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Роли в команде</h3>
          <p className="mt-0.5 text-sm text-muted">
            Отдельный профиль для части команды: аналитику и инженеру важны разные темы.
          </p>
        </div>
        <Button size="sm" icon={<Plus size={15} />} onClick={() => onEdit(null)}>
          Новая роль
        </Button>
      </div>
      {team.roles.length > 0 && (
        <ul aria-label="Роли" className="mt-4 grid gap-3 xl:grid-cols-2">
          {team.roles.map((role) => {
            const count = team.members.filter((member) => member.role_id === role.id).length
            return (
              <li key={role.id} className="rounded-2xl border border-border p-4">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold break-words">{role.name}</p>
                    <p className="text-xs text-muted">
                      {count ? `${count} ${people(count)}` : 'Пока никого'}
                      {role.spec.audience === 'management' && ' · брифинг руководителя'}
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label={`Изменить роль «${role.name}»`}
                    onClick={() => onEdit(role)}
                    className="button button--ghost button--icon-only button--sm text-muted"
                  >
                    <PenLine size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Удалить роль «${role.name}»`}
                    disabled={remove.isPending}
                    onClick={() => {
                      const question = `Удалить роль «${role.name}»? Её сотрудники вернутся к профилю команды.`
                      if (!window.confirm(question)) return
                      remove.mutate(
                        { teamId: team.id, id: role.id },
                        { onSuccess: () => toast.success('Роль удалена') },
                      )
                    }}
                    className="button button--ghost button--icon-only button--sm text-muted"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                {role.description && (
                  <p className="mt-2 line-clamp-2 text-xs text-muted">{role.description}</p>
                )}
                <div className="mt-2 flex flex-wrap gap-1">
                  {role.spec.interests.slice(0, 4).map((interest) => (
                    <Chip key={interest.id} tone="accent" className="!py-0.5 text-xs">
                      {interest.title}
                    </Chip>
                  ))}
                  {role.spec.interests.length > 4 && (
                    <Chip className="!py-0.5 text-xs">+{role.spec.interests.length - 4}</Chip>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-2 -ml-2"
                  icon={<SlidersHorizontal size={14} />}
                  onClick={() => onPatch(role)}
                >
                  Изменить профили роли
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      <ErrorNote error={remove.error} />
    </Card>
  )
}

/** What to do with the ticked people: one change for them, or another team. */
function SelectionBar({
  team,
  teams,
  selected,
  onPatch,
  onClear,
}: {
  team: Team
  teams: Team[]
  selected: string[]
  onPatch: () => void
  onClear: () => void
}) {
  const move = useMoveMembers()
  const others = teams.filter((item) => item.id !== team.id)
  return (
    <motion.div
      role="region"
      aria-label="Выбранные сотрудники"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.2, ease: EASE }}
      className="fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20 mx-auto flex max-w-2xl flex-wrap items-center gap-2 rounded-2xl bg-background-inverse py-2 pr-2 pl-4 text-sm text-background shadow-overlay md:bottom-6"
    >
      <span className="py-1 font-medium">Выбрано: {selected.length}</span>
      {/* On a phone the actions take a row of their own under the count. */}
      <button
        type="button"
        aria-label="Снять выбор"
        onClick={onClear}
        className="ml-auto grid size-9 place-items-center rounded-full hover:bg-background/10 sm:order-last sm:ml-0"
      >
        <X size={16} />
      </button>
      <div className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
        <Button
          size="sm"
          variant="primary"
          icon={<SlidersHorizontal size={14} />}
          onClick={onPatch}
        >
          Изменить профили
        </Button>
        {others.length > 0 && (
          <div className="min-w-0 flex-1 text-foreground sm:w-48 sm:flex-none">
            <SelectField
              label="Перевести в команду"
              value=""
              disabled={move.isPending}
              onChange={(teamId) => {
                const target = teams.find((item) => item.id === teamId)
                if (!target) return
                move.mutate(
                  { memberIds: selected, teamId },
                  {
                    onSuccess: (moved) => {
                      toast.success(`Переведено в «${target.name}»: ${moved.length}`)
                      onClear()
                    },
                    onError: (error) => toast.error(error.message),
                  },
                )
              }}
              options={[
                { value: '', label: 'Перевести в…', disabled: true },
                ...others.map((item) => ({ value: item.id, label: item.name })),
              ]}
            />
          </div>
        )}
      </div>
    </motion.div>
  )
}

/** One team: the profile its people get, its roles, and the people with their links. */
export function TeamPanel({ team, teams, onEdit, onDeleted }: Props) {
  const remove = useDeleteTeam()
  const [isAdding, setIsAdding] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [patching, setPatching] = useState<PatchTarget | null>(null)
  const [roleEditing, setRoleEditing] = useState<{ role: Role | null } | null>(null)
  const waiting = team.members.filter((member) => member.status === 'invited')
  // People who left the team (moved or removed) are no longer ticked.
  const ticked = selected.filter((id) => team.members.some((member) => member.id === id))
  const { spec } = team

  return (
    <div className="min-w-0 space-y-5">
      <Card className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start gap-4">
          <ProfileAvatar profile={team} size={52} />
          <div className="min-w-0 flex-1 basis-56">
            <h2 className="text-lg font-semibold break-words">{team.name}</h2>
            {team.services && (
              <p className="mt-1 text-sm whitespace-pre-line text-muted">{team.services}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" icon={<PenLine size={14} />} onClick={onEdit}>
              Изменить
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon={<Trash2 size={14} />}
              isBusy={remove.isPending}
              disabled={team.members.length > 0}
              title={
                team.members.length > 0
                  ? 'Сначала переведите сотрудников в другую команду или удалите их'
                  : undefined
              }
              onClick={() => {
                if (!window.confirm(`Удалить команду «${team.name}»?`)) return
                remove.mutate(team.id, {
                  onSuccess: () => {
                    toast.success('Команда удалена')
                    onDeleted()
                  },
                })
              }}
            >
              Удалить
            </Button>
          </div>
        </div>
        <ErrorNote error={remove.error} />

        <section aria-label="Профиль команды" className="mt-5 border-t border-separator pt-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Что получат сотрудники</h3>
            <Button
              size="sm"
              variant="ghost"
              icon={<SlidersHorizontal size={14} />}
              disabled={team.members.length === 0}
              onClick={() => setPatching({ scope: 'team' })}
            >
              Изменить профили всем
            </Button>
          </div>
          {spec.role && <p className="mt-1.5 max-w-3xl text-sm text-muted">{spec.role}</p>}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {spec.interests.map((interest) => (
              <Chip key={interest.id} tone="accent" hint={interest.description || undefined}>
                {interest.title}
              </Chip>
            ))}
          </div>
          {spec.systems && spec.systems.length > 0 && (
            <p className="mt-3 text-sm">
              <span className="text-muted">Системы: </span>
              {spec.systems.join(', ')}
            </p>
          )}
          <p className="mt-3 text-xs text-muted">
            Каждый сотрудник получает копию с должностью в начале роли. Изменения команды доходят до
            всех, кто не правил профиль сам.
          </p>
        </section>
      </Card>

      <Roles
        team={team}
        onEdit={(role) => setRoleEditing({ role })}
        onPatch={(role) => setPatching({ scope: 'role', role_id: role.id })}
      />

      <Card className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-base font-semibold">
            Сотрудники
            {team.members.length > 0 && (
              <span className="ml-2 font-normal text-muted tabular-nums">
                {team.members.length}
              </span>
            )}
          </h3>
          <div className="flex flex-wrap gap-2">
            {waiting.length > 1 && (
              <Button
                size="sm"
                icon={<ContentCopy size={14} />}
                onClick={() => void copyText(invitationsText(waiting), 'Приглашения скопированы')}
              >
                Скопировать {waiting.length}{' '}
                {plural(waiting.length, ['приглашение', 'приглашения', 'приглашений'])}
              </Button>
            )}
            <Button
              size="sm"
              variant="primary"
              icon={<UserPlus size={15} />}
              onClick={() => setIsAdding(true)}
            >
              Добавить сотрудников
            </Button>
          </div>
        </div>
        {team.members.length > 0 ? (
          <div className="mt-3">
            <MemberList team={team} teams={teams} selected={ticked} onSelect={setSelected} />
          </div>
        ) : (
          <EmptyState icon={<Users />} title="В команде пока никого">
            Вставьте список сотрудников, и сервис заведёт каждому аккаунт с профилем команды.
          </EmptyState>
        )}
      </Card>

      {ticked.length > 0 && <div aria-hidden className="h-20" />}
      <AnimatePresence>
        {ticked.length > 0 && (
          <SelectionBar
            team={team}
            teams={teams}
            selected={ticked}
            onPatch={() => setPatching({ scope: 'people', member_ids: ticked })}
            onClear={() => setSelected([])}
          />
        )}
      </AnimatePresence>

      <AddPeopleDialog team={team} open={isAdding} onOpenChange={setIsAdding} />
      {patching && (
        <PatchDialog
          team={team}
          selected={ticked}
          initial={patching}
          onClose={() => setPatching(null)}
        />
      )}
      {roleEditing && (
        <RoleEditor
          key={roleEditing.role?.id ?? 'new'}
          team={team}
          role={roleEditing.role}
          onClose={() => setRoleEditing(null)}
        />
      )}
    </div>
  )
}
