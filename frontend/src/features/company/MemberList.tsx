import clsx from 'clsx'
import { useState } from 'react'
import type { DragEvent } from 'react'
import { ContentCopy, PenLine, RefreshCw, RotateCcw, Trash2 } from '../../components/icons'
import { SelectField } from '../../components/SelectField'
import { INPUT_CLASS } from '../../components/tokens'
import { Button, Chip, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import { UserAvatar } from '../../components/UserAvatar'
import { inviteUrl } from '../../lib/company'
import type { Member, Team } from '../../lib/company'
import {
  useRemoveMember,
  useRenewInvite,
  useResetOverrides,
  useUpdateMember,
} from '../../lib/companyQueries'
import { formatDate, formatRelative, plural } from '../../lib/format'
import { toast } from '../../lib/toast'
import { copyText } from './copy'
import { DRAG_TYPE } from './drag'

/** Where the person stands, in words and a tone: the colour is never the only sign. */
function StatusChip({ member }: { member: Member }) {
  if (member.status === 'active') {
    return (
      <Chip
        tone="ok"
        title={
          member.last_login_at
            ? `Последний вход ${formatRelative(member.last_login_at)}`
            : undefined
        }
      >
        В сервисе
      </Chip>
    )
  }
  if (member.status === 'invited') {
    return (
      <Chip
        tone="spark"
        title={
          member.invite_expires_at
            ? `Ссылка действует до ${formatDate(member.invite_expires_at)}`
            : undefined
        }
      >
        Ждёт входа
      </Chip>
    )
  }
  return <Chip tone="danger">Ссылка устарела</Chip>
}

async function copyInvite(member: Member) {
  const url = inviteUrl(member)
  if (url) await copyText(url, `Ссылка для ${member.display_name} скопирована`)
}

const NO_ROLE = ''

type DialogProps = {
  member: Member
  teams: Team[]
  onClose: () => void
}

/** One person: name, position, team and role, their own changes, a link, or removal. */
function MemberDialog({ member, teams, onClose }: DialogProps) {
  const update = useUpdateMember()
  const renew = useRenewInvite()
  const remove = useRemoveMember()
  const reset = useResetOverrides()
  const [name, setName] = useState(member.display_name)
  const [jobTitle, setJobTitle] = useState(member.job_title ?? '')
  const [teamId, setTeamId] = useState(member.team_id ?? '')
  const [roleId, setRoleId] = useState(member.role_id ?? NO_ROLE)
  const isBusy = update.isPending || renew.isPending || remove.isPending || reset.isPending
  const isMoving = teamId !== member.team_id
  const roles = teams.find((team) => team.id === teamId)?.roles ?? []
  const isRoleChanged = !isMoving && roleId !== (member.role_id ?? NO_ROLE)
  const isChanged =
    name.trim() !== member.display_name ||
    jobTitle.trim() !== (member.job_title ?? '') ||
    isMoving ||
    isRoleChanged ||
    (isMoving && roleId !== NO_ROLE)

  const save = () =>
    update.mutate(
      {
        id: member.id,
        change: {
          ...(name.trim() !== member.display_name && { display_name: name.trim() }),
          ...(jobTitle.trim() !== (member.job_title ?? '') && { job_title: jobTitle.trim() }),
          ...(isMoving && { team_id: teamId }),
          // In a new team the role a position names is picked unless one is chosen.
          ...((isRoleChanged || (isMoving && roleId !== NO_ROLE)) && {
            role_id: roleId || null,
          }),
        },
      },
      {
        onSuccess: () => {
          toast.success('Сотрудник сохранён')
          onClose()
        },
      },
    )

  return (
    <Dialog open onOpenChange={(open) => !open && !isBusy && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{member.display_name}</DialogTitle>
          <DialogDescription>{member.email}</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (isChanged && name.trim().length >= 2) save()
          }}
        >
          <Field label="Имя">
            <input
              required
              minLength={2}
              maxLength={80}
              className={INPUT_CLASS}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Должность" hint="руководителю достаётся брифинг">
            <input
              maxLength={120}
              className={INPUT_CLASS}
              value={jobTitle}
              onChange={(event) => setJobTitle(event.target.value)}
            />
          </Field>
          {teams.length > 1 && (
            <Field label="Команда" isGroup>
              <SelectField
                label="Команда"
                value={teamId}
                onChange={(next) => {
                  setTeamId(next)
                  setRoleId(next === member.team_id ? (member.role_id ?? NO_ROLE) : NO_ROLE)
                }}
                options={teams.map((team) => ({ value: team.id, label: team.name }))}
              />
            </Field>
          )}
          {roles.length > 0 && (
            <Field label="Роль в команде" isGroup>
              <SelectField
                label="Роль в команде"
                value={roleId}
                onChange={setRoleId}
                options={[
                  { value: NO_ROLE, label: isMoving ? 'По должности' : 'Без роли' },
                  ...roles.map((role) => ({ value: role.id, label: role.name })),
                ]}
              />
            </Field>
          )}
          <p className="text-xs text-muted">
            Профиль команды у сотрудника обновится сам. Профили, которые он правил сам, останутся
            как есть.
          </p>
          <ErrorNote error={update.error ?? renew.error ?? remove.error ?? reset.error} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button disabled={isBusy} onClick={onClose}>
              Отмена
            </Button>
            <Button
              type="submit"
              variant="primary"
              isBusy={update.isPending}
              disabled={!isChanged || name.trim().length < 2}
            >
              Сохранить
            </Button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2 border-t border-separator pt-4">
          {member.overrides > 0 && (
            <Button
              size="sm"
              icon={<RotateCcw size={14} />}
              isBusy={reset.isPending}
              disabled={isBusy}
              onClick={() =>
                reset.mutate(member.id, {
                  onSuccess: () => toast.success('Личные правки сброшены'),
                })
              }
            >
              Сбросить личные правки ({member.overrides})
            </Button>
          )}
          {member.status !== 'active' && (
            <Button
              size="sm"
              icon={<RefreshCw size={14} />}
              isBusy={renew.isPending}
              disabled={isBusy}
              onClick={() =>
                renew.mutate(member.id, {
                  onSuccess: (renewed) => void copyInvite(renewed),
                })
              }
            >
              Новая ссылка
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            icon={<Trash2 size={14} />}
            isBusy={remove.isPending}
            disabled={isBusy}
            onClick={() => {
              const question = `Удалить аккаунт «${member.display_name}»? Профили, выпуски и отметки сотрудника удалятся вместе с ним.`
              if (!window.confirm(question)) return
              remove.mutate(member.id, {
                onSuccess: () => {
                  toast.success('Аккаунт удалён')
                  onClose()
                },
              })
            }}
          >
            Удалить аккаунт
          </Button>
        </div>
        {member.status !== 'active' && (
          <p className="-mt-2 text-xs text-muted">
            Новая ссылка сразу скопируется, а старая перестанет работать.
          </p>
        )}
      </DialogContent>
    </Dialog>
  )
}

type Props = {
  team: Team
  teams: Team[]
  /** The people ticked for one change or one move. */
  selected: string[]
  onSelect: (ids: string[]) => void
}

/**
 * The people of a team: who came in, who still has a link waiting, their role
 * and own changes. Ticked people change together; a row dragged onto another
 * team in the list on the left moves there, with everyone ticked beside it.
 */
export function MemberList({ team, teams, selected, onSelect }: Props) {
  const [editing, setEditing] = useState<Member | null>(null)
  const [dragging, setDragging] = useState<string[]>([])
  const roles = new Map(team.roles.map((role) => [role.id, role.name]))
  const canMove = teams.length > 1
  const isAll = team.members.length > 0 && selected.length === team.members.length

  const toggle = (id: string) =>
    onSelect(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id])

  const startDrag = (event: DragEvent, member: Member) => {
    const ids = selected.includes(member.id) ? selected : [member.id]
    event.dataTransfer.setData(DRAG_TYPE, JSON.stringify(ids))
    event.dataTransfer.effectAllowed = 'move'
    setDragging(ids)
  }

  return (
    <>
      <label className="flex items-center gap-2 border-b border-separator pb-2 text-xs text-muted">
        <input
          type="checkbox"
          className="size-4 accent-[var(--accent)]"
          checked={isAll}
          onChange={() => onSelect(isAll ? [] : team.members.map((member) => member.id))}
        />
        {isAll ? 'Снять выбор' : 'Выбрать всех'}
        {canMove && (
          <span className="ml-auto hidden lg:inline">
            Перетащите строку на команду слева, чтобы перевести человека
          </span>
        )}
      </label>
      <ul className="divide-y divide-separator">
        {team.members.map((member) => {
          const isChosen = selected.includes(member.id)
          return (
            <li
              key={member.id}
              draggable={canMove}
              onDragStart={(event) => startDrag(event, member)}
              onDragEnd={() => setDragging([])}
              className={clsx(
                'flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl px-1 py-3 transition-colors',
                canMove && 'lg:cursor-grab',
                isChosen && 'bg-accent-soft/60',
                dragging.includes(member.id) && 'opacity-50',
              )}
            >
              <input
                type="checkbox"
                aria-label={`Выбрать: ${member.display_name}`}
                className="size-4 shrink-0 accent-[var(--accent)]"
                checked={isChosen}
                onChange={() => toggle(member.id)}
              />
              <UserAvatar
                me={{
                  display_name: member.display_name,
                  avatar_url: null,
                  avatar_preset: member.avatar_preset,
                }}
                size={40}
              />
              <div className="min-w-0 flex-1 basis-40">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-medium">
                  <span className="break-words">{member.display_name}</span>
                  {member.role_id && roles.has(member.role_id) && (
                    <Chip tone="accent" className="!py-0.5 text-xs">
                      {roles.get(member.role_id)}
                    </Chip>
                  )}
                  {member.audience === 'management' && (
                    <Chip className="!py-0.5 text-xs" hint="Получает краткий брифинг руководителя">
                      брифинг
                    </Chip>
                  )}
                  {member.overrides > 0 && (
                    <Chip
                      className="!py-0.5 text-xs"
                      hint="Правки профиля только для этого человека: сохраняются при изменениях команды"
                    >
                      {member.overrides}{' '}
                      {plural(member.overrides, ['своя правка', 'свои правки', 'своих правок'])}
                    </Chip>
                  )}
                </p>
                <p className="truncate text-xs text-muted">
                  {[member.job_title, member.email].filter(Boolean).join(' · ')}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <StatusChip member={member} />
                {member.status === 'invited' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<ContentCopy size={14} />}
                    aria-label={`Скопировать приглашение для ${member.display_name}`}
                    onClick={() => void copyInvite(member)}
                  >
                    <span className="hidden sm:inline">Ссылка</span>
                  </Button>
                )}
                <button
                  type="button"
                  aria-label={`Изменить: ${member.display_name}`}
                  onClick={() => setEditing(member)}
                  className="button button--ghost button--icon-only button--sm text-muted"
                >
                  <PenLine size={15} />
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      {editing && (
        <MemberDialog
          key={editing.id}
          member={editing}
          teams={teams}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}
