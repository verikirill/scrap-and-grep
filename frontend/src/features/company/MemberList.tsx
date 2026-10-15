import { useState } from 'react'
import { ContentCopy, PenLine, RefreshCw, Trash2 } from '../../components/icons'
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
import { useRemoveMember, useRenewInvite, useUpdateMember } from '../../lib/companyQueries'
import { formatDate, formatRelative } from '../../lib/format'
import { toast } from '../../lib/toast'
import { copyText } from './copy'

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

type DialogProps = {
  member: Member
  teams: Team[]
  onClose: () => void
}

/** One person: name, position and team, a fresh link, or removal from the company. */
function MemberDialog({ member, teams, onClose }: DialogProps) {
  const update = useUpdateMember()
  const renew = useRenewInvite()
  const remove = useRemoveMember()
  const [name, setName] = useState(member.display_name)
  const [jobTitle, setJobTitle] = useState(member.job_title ?? '')
  const [teamId, setTeamId] = useState(member.team_id ?? '')
  const isBusy = update.isPending || renew.isPending || remove.isPending
  const isChanged =
    name.trim() !== member.display_name ||
    jobTitle.trim() !== (member.job_title ?? '') ||
    teamId !== member.team_id

  const save = () =>
    update.mutate(
      {
        id: member.id,
        change: {
          ...(name.trim() !== member.display_name && { display_name: name.trim() }),
          ...(jobTitle.trim() !== (member.job_title ?? '') && { job_title: jobTitle.trim() }),
          ...(teamId !== member.team_id && { team_id: teamId }),
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
                onChange={setTeamId}
                options={teams.map((team) => ({ value: team.id, label: team.name }))}
              />
            </Field>
          )}
          <p className="text-xs text-muted">
            При смене команды или должности профиль команды у сотрудника обновится. Профили, которые
            он правил сам, останутся как есть.
          </p>
          <ErrorNote error={update.error ?? renew.error ?? remove.error} />
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
  members: Member[]
  teams: Team[]
}

/** The people of a team: who came in, who still has a link waiting, and what to do next. */
export function MemberList({ members, teams }: Props) {
  const [editing, setEditing] = useState<Member | null>(null)
  return (
    <>
      <ul className="divide-y divide-separator">
        {members.map((member) => (
          <li key={member.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
            <UserAvatar
              me={{
                display_name: member.display_name,
                avatar_url: null,
                avatar_preset: member.avatar_preset,
              }}
              size={40}
            />
            <div className="min-w-0 flex-1 basis-40">
              <p className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
                <span className="break-words">{member.display_name}</span>
                {member.audience === 'management' && (
                  <Chip className="!py-0.5 text-xs" hint="Получает краткий брифинг руководителя">
                    брифинг
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
        ))}
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
