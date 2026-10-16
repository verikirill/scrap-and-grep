import { useMemo, useState } from 'react'
import { CircleCheck, ContentCopy, TriangleAlert } from '../../components/icons'
import { SelectField } from '../../components/SelectField'
import { TEXTAREA_CLASS } from '../../components/tokens'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { MembersAdded, Team } from '../../lib/company'
import { inviteUrl } from '../../lib/company'
import { useAddMembers } from '../../lib/companyQueries'
import { plural } from '../../lib/format'
import { MAX_PEOPLE, parsePeople } from '../../lib/people'
import { copyText, invitationsText } from './copy'

const EXAMPLE = [
  'Анна Смирнова, anna@company.ru, ведущий инженер SOC',
  'Олег Петров, oleg@company.ru, начальник отдела мониторинга',
].join('\n')

const people = (count: number) => plural(count, ['сотрудника', 'сотрудников', 'сотрудников'])

type Props = {
  team: Team
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** What came out of the list: the accounts made, each with its link, and the lines left out. */
function Result({ result, onDone }: { result: MembersAdded; onDone: () => void }) {
  const text = invitationsText(result.created)
  return (
    <div className="space-y-4">
      {result.created.length > 0 && (
        <section aria-label="Готовые аккаунты" className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-medium">
              <CircleCheck size={18} className="text-success" />
              Аккаунты готовы: {result.created.length}
            </p>
            <Button
              size="sm"
              variant="primary"
              icon={<ContentCopy size={15} />}
              onClick={() => void copyText(text, 'Приглашения скопированы')}
            >
              Скопировать все приглашения
            </Button>
          </div>
          <p className="text-xs text-muted">
            Отправьте каждому его ссылку в почте или мессенджере. По ссылке человек задаёт пароль и
            сразу попадает в сервис с профилем команды. Ссылки всегда можно скопировать снова в
            списке сотрудников.
          </p>
          <ul className="max-h-64 space-y-1.5 overflow-y-auto">
            {result.created.map((member) => (
              <li
                key={member.id}
                className="flex items-center gap-3 rounded-2xl bg-surface-secondary px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{member.display_name}</p>
                  <p className="truncate text-xs text-muted">{member.email}</p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<ContentCopy size={14} />}
                  onClick={() => {
                    const url = inviteUrl(member)
                    if (url) void copyText(url, `Ссылка для ${member.display_name} скопирована`)
                  }}
                >
                  Ссылка
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {result.skipped.length > 0 && (
        <section aria-label="Не добавлены" className="space-y-2">
          <p className="flex items-center gap-2 text-sm font-medium">
            <TriangleAlert size={17} className="text-warning" />
            Не добавлены: {result.skipped.length}
          </p>
          <ul className="space-y-1 text-sm">
            {result.skipped.map((item) => (
              <li key={item.email} className="flex flex-wrap gap-x-2">
                <span className="font-medium break-all">{item.email}</span>
                <span className="text-muted">{item.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="flex justify-end">
        <Button variant="primary" onClick={onDone}>
          Готово
        </Button>
      </div>
    </div>
  )
}

/**
 * People for a team, pasted as a list: a line each, with a name, an address
 * and a position. The preview shows how each line was read before anything
 * is made; then every person gets an account and a link of their own.
 */
export function AddPeopleDialog({ team, open, onOpenChange }: Props) {
  const add = useAddMembers()
  const [text, setText] = useState('')
  const [result, setResult] = useState<MembersAdded | null>(null)
  const [roleId, setRoleId] = useState('')
  const rows = useMemo(() => parsePeople(text), [text])
  const ready = rows.filter((row) => row.problem === null)
  const isTooMany = ready.length > MAX_PEOPLE

  const close = () => {
    onOpenChange(false)
    setText('')
    setResult(null)
    add.reset()
  }

  const submit = () =>
    add.mutate(
      {
        teamId: team.id,
        people: ready.map(({ name, email, job_title }) => ({ name, email, job_title })),
        roleId: roleId || null,
      },
      { onSuccess: setResult },
    )

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !add.isPending && (next ? onOpenChange(true) : close())}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Сотрудники в команду «{team.name}»</DialogTitle>
          <DialogDescription>
            Сервис заведёт каждому аккаунт с профилем команды. Самим сотрудникам останется задать
            пароль по ссылке.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <Result result={result} onDone={close} />
        ) : (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              if (ready.length > 0 && !isTooMany) submit()
            }}
          >
            <Field label="Список сотрудников" hint="по одному в строке: имя, почта, должность">
              <textarea
                autoFocus
                rows={6}
                placeholder={EXAMPLE}
                className={TEXTAREA_CLASS}
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </Field>
            <p className="-mt-2 px-1 text-xs text-muted">
              Подойдут и столбцы, скопированные из таблицы. По должности сервис понимает, кому нужен
              брифинг руководителя.
            </p>

            {rows.length > 0 && (
              <div className="max-h-60 overflow-y-auto rounded-2xl border border-border">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Как прочитан список</caption>
                  <thead className="sticky top-0 bg-surface-secondary text-xs text-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">
                        Имя
                      </th>
                      <th scope="col" className="px-3 py-2 font-medium">
                        Почта
                      </th>
                      <th scope="col" className="hidden px-3 py-2 font-medium sm:table-cell">
                        Должность
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={`${index}-${row.line}`} className="border-t border-separator">
                        <td className="px-3 py-2 align-top break-words">
                          {row.name || <span className="text-muted">по почте</span>}
                        </td>
                        <td className="px-3 py-2 align-top break-all">
                          {row.problem ? (
                            <span className="text-danger">{row.problem}</span>
                          ) : (
                            row.email
                          )}
                        </td>
                        <td className="hidden px-3 py-2 align-top break-words text-muted sm:table-cell">
                          {row.job_title}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {team.roles.length > 0 && (
              <Field label="Роль в команде" isGroup>
                <SelectField
                  label="Роль в команде"
                  value={roleId}
                  onChange={setRoleId}
                  options={[
                    { value: '', label: 'По должности каждого' },
                    ...team.roles.map((role) => ({ value: role.id, label: `Всем: ${role.name}` })),
                  ]}
                />
              </Field>
            )}

            {isTooMany && (
              <p className="text-sm text-warning">
                За раз можно добавить до {MAX_PEOPLE} человек: разбейте список на части.
              </p>
            )}
            <ErrorNote error={add.error} />
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button disabled={add.isPending} onClick={close}>
                Отмена
              </Button>
              <Button
                type="submit"
                variant="primary"
                isBusy={add.isPending}
                disabled={ready.length === 0 || isTooMany}
              >
                {ready.length > 0
                  ? `Добавить ${ready.length} ${people(ready.length)}`
                  : 'Добавить сотрудников'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
