import { useState } from 'react'
import { Layers, Sparkles } from '../../components/icons'
import { INPUT_CLASS, TEXTAREA_CLASS } from '../../components/tokens'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { ProfileSpec } from '../../lib/api'
import type { Role, Team } from '../../lib/company'
import { useDraftRole, useSaveRole } from '../../lib/companyQueries'
import { toast } from '../../lib/toast'
import { SpecReview } from './SpecReview'

type Props = {
  team: Team
  /** The role to change; null makes a new one. */
  role: Role | null
  onClose: () => void
}

/**
 * A role within a team: «Аналитик» and «Инженер» of one SOC read differently.
 * The profile starts from the team's or is drafted from what the role does;
 * people whose position names the role get it by themselves.
 */
export function RoleEditor({ team, role, onClose }: Props) {
  const draft = useDraftRole()
  const save = useSaveRole()
  const [name, setName] = useState(role?.name ?? '')
  const [description, setDescription] = useState(role?.description ?? '')
  const [spec, setSpec] = useState<ProfileSpec | null>(role?.spec ?? null)
  const [draftedBy, setDraftedBy] = useState<string | null>(null)
  const isNameShort = name.trim().length < 2

  const pick = () =>
    draft.mutate(
      { teamId: team.id, role: { name: name.trim(), description: description.trim() } },
      {
        onSuccess: (result) => {
          setSpec(result.spec)
          setDraftedBy(result.drafted_by)
        },
      },
    )

  const submit = () =>
    save.mutate(
      {
        teamId: team.id,
        id: role?.id ?? null,
        role: { name: name.trim(), description: description.trim(), spec: spec ?? undefined },
      },
      {
        onSuccess: (saved) => {
          toast.success(role ? 'Роль сохранена' : `Роль «${saved.name}» добавлена`)
          onClose()
        },
      },
    )

  return (
    <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{role ? `Роль «${role.name}»` : `Новая роль в «${team.name}»`}</DialogTitle>
          <DialogDescription>
            Роль нужна, когда люди одной команды читают разное: например, аналитику и инженеру ИБ
            важны разные темы. Сотрудники с ролью получают её профиль вместо общего.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (spec) submit()
            else pick()
          }}
        >
          <Field label="Название роли" hint="по нему роль находит людей по должности">
            <input
              required
              autoFocus={!role}
              minLength={2}
              maxLength={80}
              placeholder="Аналитик, Инженер АСУ ТП, Руководитель"
              className={INPUT_CLASS}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Чем роль отличается" hint="необязательно">
            <textarea
              maxLength={2000}
              rows={3}
              placeholder="Разбирает угрозы, пишет отчёты для руководства, следит за APT-группировками в энергетике."
              className={TEXTAREA_CLASS}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>

          {!spec && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="submit"
                variant="primary"
                icon={<Sparkles size={15} />}
                isBusy={draft.isPending}
                disabled={isNameShort}
              >
                Подобрать темы
              </Button>
              <Button
                icon={<Layers size={15} />}
                disabled={isNameShort || draft.isPending}
                onClick={() => setSpec({ ...team.spec, name: `${team.name}: ${name.trim()}` })}
              >
                Начать с профиля команды
              </Button>
              {draft.isPending && (
                <span aria-live="polite" className="text-sm text-muted">
                  Читаем описание роли и команды
                </span>
              )}
            </div>
          )}
          <ErrorNote error={draft.error} />
          {spec && (
            <SpecReview
              spec={spec}
              onChange={setSpec}
              title="Профиль роли"
              draftedBy={draftedBy}
              withAudience
            />
          )}

          <ErrorNote error={save.error} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button disabled={save.isPending} onClick={onClose}>
              Отмена
            </Button>
            <Button
              variant="primary"
              disabled={isNameShort || !spec || draft.isPending}
              isBusy={save.isPending}
              onClick={submit}
            >
              {role ? 'Сохранить' : 'Добавить роль'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
