import { useState } from 'react'
import { ContentCopy, PenLine, Trash2, UserPlus, Users } from '../../components/icons'
import { Button, Card, Chip, EmptyState, ErrorNote } from '../../components/ui'
import type { Team } from '../../lib/company'
import { useDeleteTeam } from '../../lib/companyQueries'
import { plural } from '../../lib/format'
import { toast } from '../../lib/toast'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { AddPeopleDialog } from './AddPeopleDialog'
import { copyText, invitationsText } from './copy'
import { MemberList } from './MemberList'

type Props = {
  team: Team
  teams: Team[]
  onEdit: () => void
  onDeleted: () => void
}

/** One team: the profile its people get, and the people with their links. */
export function TeamPanel({ team, teams, onEdit, onDeleted }: Props) {
  const remove = useDeleteTeam()
  const [isAdding, setIsAdding] = useState(false)
  const waiting = team.members.filter((member) => member.status === 'invited')
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
          <h3 className="text-sm font-semibold">Что получат сотрудники</h3>
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
          <div className="mt-2">
            <MemberList members={team.members} teams={teams} />
          </div>
        ) : (
          <EmptyState icon={<Users />} title="В команде пока никого">
            Вставьте список сотрудников, и сервис заведёт каждому аккаунт с профилем команды.
          </EmptyState>
        )}
      </Card>

      <AddPeopleDialog team={team} open={isAdding} onOpenChange={setIsAdding} />
    </div>
  )
}
