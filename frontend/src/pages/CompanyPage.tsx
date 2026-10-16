import clsx from 'clsx'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { PenLine, Plus, Sparkles, Users } from '../components/icons'
import { Loading, Skeleton, SkeletonText } from '../components/loading'
import { Button, Card, EmptyState, ErrorState, PageHeader } from '../components/ui'
import { CompanyDialog } from '../features/company/CompanyDialog'
import { CreateCompany } from '../features/company/CreateCompany'
import { TeamEditor } from '../features/company/TeamEditor'
import { TeamPanel } from '../features/company/TeamPanel'
import { CompanyLogo } from '../features/company/CompanyLogo'
import { ProfileAvatar } from '../features/profiles/ProfileLook'
import { quoted } from '../lib/company'
import type { Company, Team } from '../lib/company'
import { useCompany, useMoveMembers } from '../lib/companyQueries'
import { useMe } from '../lib/queries'
import { DRAG_TYPE, droppedMembers } from '../features/company/drag'
import { toast } from '../lib/toast'
import { plural } from '../lib/format'

const TITLE = 'Компания'

/** «4 сотрудника, 1 ждёт входа»: a team at a glance. */
function teamLine(team: Team): string {
  const count = team.members.length
  if (count === 0) return 'Пока без сотрудников'
  const waiting = team.members.filter((member) => member.status !== 'active').length
  const people = `${count} ${plural(count, ['сотрудник', 'сотрудника', 'сотрудников'])}`
  return waiting
    ? `${people}, ${waiting} ${plural(waiting, ['ждёт', 'ждут', 'ждут'])} входа`
    : people
}

function Totals({ company }: { company: Company }) {
  const members = company.teams.flatMap((team) => team.members)
  const active = members.filter((member) => member.status === 'active').length
  const items = [
    {
      value: company.teams.length,
      label: plural(company.teams.length, ['команда', 'команды', 'команд']),
    },
    {
      value: members.length,
      label: plural(members.length, ['сотрудник', 'сотрудника', 'сотрудников']),
    },
    { value: active, label: 'уже в сервисе' },
  ]
  return (
    <dl className="mb-5 grid grid-cols-3 gap-3 sm:max-w-lg">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex flex-col-reverse rounded-2xl bg-surface px-4 py-3 shadow-surface"
        >
          <dt className="text-xs text-muted">{item.label}</dt>
          <dd className="text-xl font-semibold tabular-nums">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

type Editing = { team: Team | null } | null

function Space({ company }: { company: Company }) {
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState<Editing>(null)
  const [isAbout, setIsAbout] = useState(false)
  const chosen = params.get('team')
  const team = company.teams.find((item) => item.id === chosen) ?? company.teams[0] ?? null

  const move = useMoveMembers()
  const [dropTarget, setDropTarget] = useState<string | null>(null)

  /** People dropped on a team move there; their own team cannot take them twice. */
  const dropOn = (target: Team, ids: string[]) => {
    const moving = ids.filter((id) => !target.members.some((member) => member.id === id))
    if (moving.length === 0) return
    move.mutate(
      { memberIds: moving, teamId: target.id },
      {
        onSuccess: (moved) =>
          toast.success(
            moved.length === 1
              ? `${moved[0].display_name} теперь в «${target.name}»`
              : `Переведено в «${target.name}»: ${moved.length}`,
          ),
        onError: (error) => toast.error(error.message),
      },
    )
  }

  const select = (id: string | null) =>
    setParams(id ? { team: id } : {}, { replace: true, preventScrollReset: true })

  return (
    <>
      <PageHeader
        title={TITLE}
        subtitle={
          <span className="flex items-center gap-3">
            <CompanyLogo name={company.name} logoUrl={company.logo_url} size={44} />
            <span>
              <span className="font-medium text-foreground">{company.name}</span>
              {company.about && `. ${company.about}`}
            </span>
          </span>
        }
        actions={
          <>
            <Button variant="ghost" icon={<PenLine size={15} />} onClick={() => setIsAbout(true)}>
              О компании
            </Button>
            <Button
              variant="primary"
              icon={<Plus size={16} />}
              onClick={() => setEditing({ team: null })}
            >
              Новая команда
            </Button>
          </>
        }
      />

      {company.teams.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Sparkles />}
            title="Добавьте первую команду"
            action={
              <Button
                variant="primary"
                icon={<Plus size={16} />}
                onClick={() => setEditing({ team: null })}
              >
                Новая команда
              </Button>
            }
          >
            Опишите, чем занимается команда и какие сервисы ведёт. Сервис подберёт по описанию темы
            новостей, а вы проверите их перед сохранением.
          </EmptyState>
        </Card>
      ) : (
        <>
          <Totals company={company} />
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
            <nav aria-label="Команды" className="lg:sticky lg:top-9 lg:self-start">
              <Card className="p-2">
                <ul className="space-y-1">
                  {company.teams.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => select(item.id)}
                        aria-current={item.id === team?.id ? 'true' : undefined}
                        // Member rows dragged here move to this team.
                        onDragOver={(event) => {
                          if (!event.dataTransfer.types.includes(DRAG_TYPE)) return
                          event.preventDefault()
                          event.dataTransfer.dropEffect = 'move'
                          setDropTarget(item.id)
                        }}
                        onDragLeave={() => setDropTarget(null)}
                        onDrop={(event) => {
                          event.preventDefault()
                          setDropTarget(null)
                          dropOn(item, droppedMembers(event.dataTransfer))
                        }}
                        className={clsx(
                          'flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors',
                          dropTarget === item.id
                            ? 'bg-accent-soft ring-2 ring-accent'
                            : item.id === team?.id
                              ? 'bg-accent-soft ring-1 ring-accent/40'
                              : 'hover:bg-default/60',
                        )}
                      >
                        <ProfileAvatar profile={item} size={36} />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium break-words">{item.name}</span>
                          <span className="block text-xs text-muted">{teamLine(item)}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </Card>
            </nav>
            {team && (
              <TeamPanel
                key={team.id}
                team={team}
                teams={company.teams}
                onEdit={() => setEditing({ team })}
                onDeleted={() => select(null)}
              />
            )}
          </div>
        </>
      )}

      {editing && (
        <TeamEditor
          key={editing.team?.id ?? 'new'}
          team={editing.team}
          open
          onOpenChange={(open) => !open && setEditing(null)}
          onSaved={(saved) => select(saved.id)}
        />
      )}
      {isAbout && <CompanyDialog company={company} onClose={() => setIsAbout(false)} />}
    </>
  )
}

/**
 * A company space: the manager describes the teams, and the service makes
 * accounts with ready profiles for the people in them.
 */
export function CompanyPage() {
  const me = useMe()
  const membership = me.data?.company
  const isMember = membership?.role === 'member'
  const company = useCompany(!isMember)

  // People a company added read; the space is run by its manager.
  if (isMember) {
    return (
      <>
        <PageHeader title={TITLE} />
        <Card>
          <EmptyState icon={<Users />} title={`Вы в команде «${membership?.team ?? ''}»`}>
            Пространством {quoted(membership?.company ?? '')} управляет{' '}
            {membership?.manager ?? 'руководитель'}. Команду и должность видно на странице
            «Аккаунт».
          </EmptyState>
        </Card>
      </>
    )
  }

  if (company.isPending) {
    return (
      <>
        <PageHeader title={TITLE} />
        <Loading label="Загружаем пространство" className="grid gap-5 lg:grid-cols-[18rem_1fr]">
          <div className="space-y-3 rounded-3xl bg-surface p-4 shadow-surface">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex items-center gap-3">
                <Skeleton className="size-9 rounded-full" />
                <Skeleton className="h-4 w-32" />
              </div>
            ))}
          </div>
          <div className="space-y-4 rounded-3xl bg-surface p-6 shadow-surface">
            <Skeleton className="h-6 w-48" />
            <SkeletonText lines={3} />
          </div>
        </Loading>
      </>
    )
  }
  if (company.error) {
    return (
      <>
        <PageHeader title={TITLE} />
        <Card>
          <ErrorState
            title="Пространство не загрузилось"
            error={company.error}
            action={<Button onClick={() => void company.refetch()}>Повторить</Button>}
          />
        </Card>
      </>
    )
  }
  if (!company.data) {
    return (
      <>
        <PageHeader
          title={TITLE}
          subtitle="Команды, их сервисы и аккаунты сотрудников с готовыми профилями интересов."
        />
        <CreateCompany />
      </>
    )
  }
  return <Space company={company.data} />
}
