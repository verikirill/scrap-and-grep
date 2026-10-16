import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { ChipsInput } from '../../components/ChipsInput'
import { RefreshCw, Sparkles } from '../../components/icons'
import { EASE, INPUT_CLASS, TEXTAREA_CLASS } from '../../components/tokens'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { ProfileSpec } from '../../lib/api'
import type { Team, TeamBrief } from '../../lib/company'
import { useDraftTeam, useSaveTeam } from '../../lib/companyQueries'
import { toast } from '../../lib/toast'
import { SpecReview } from './SpecReview'

const SERVICES_HINT =
  'Например: круглосуточный мониторинг событий ИБ в MaxPatrol SIEM, разбор инцидентов, правила корреляции. Ведём EDR на рабочих станциях трёх филиалов.'

type Props = {
  /** The team to change; null makes a new one. */
  team: Team | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (team: Team) => void
}

/**
 * What the draft was read from, to notice when the manager changed it since.
 * A new name alone needs no new draft.
 */
const briefKey = (brief: TeamBrief) => JSON.stringify([brief.services.trim(), brief.systems])

/**
 * A team in two steps: the manager says what it does, the service proposes the
 * profile its people get, and the manager checks it before saving. Every
 * topic can be dropped and the role reworded; nothing is saved until asked.
 */
export function TeamEditor({ team, open, onOpenChange, onSaved }: Props) {
  const draft = useDraftTeam()
  const save = useSaveTeam()
  const [brief, setBrief] = useState<TeamBrief>({
    name: team?.name ?? '',
    services: team?.services ?? '',
    systems: team?.spec.systems ?? [],
  })
  const [spec, setSpec] = useState<ProfileSpec | null>(team?.spec ?? null)
  const [draftedFrom, setDraftedFrom] = useState(team ? briefKey(brief) : null)
  const [draftedBy, setDraftedBy] = useState<string | null>(null)

  const isNameShort = brief.name.trim().length < 2
  const isStale = spec !== null && draftedFrom !== briefKey(brief)
  const canSave = !isNameShort && spec !== null && spec.interests.length > 0

  const pick = () =>
    draft.mutate(brief, {
      onSuccess: (result) => {
        // The products the model found join the manager's own list.
        const next = { ...brief, systems: result.spec.systems ?? brief.systems }
        setBrief(next)
        setSpec(result.spec)
        setDraftedFrom(briefKey(next))
        setDraftedBy(result.drafted_by)
      },
    })

  const submit = () => {
    if (!spec || !canSave) return
    const systems = brief.systems
    save.mutate(
      {
        id: team?.id ?? null,
        team: { ...brief, systems, spec: { ...spec, name: brief.name.trim(), systems } },
      },
      {
        onSuccess: (saved) => {
          toast.success(team ? 'Команда сохранена' : `Команда «${saved.name}» создана`)
          onSaved(saved)
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !save.isPending && onOpenChange(next)}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{team ? `Команда «${team.name}»` : 'Новая команда'}</DialogTitle>
          <DialogDescription>
            Опишите работу команды своими словами. Сервис подберёт по описанию темы новостей, а
            сотрудники получат готовый профиль интересов.
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
          <Field label="Название">
            <input
              required
              minLength={2}
              maxLength={120}
              autoFocus={!team}
              placeholder="SOC, Сетевая инфраструктура, Эксплуатация АСУ ТП"
              className={INPUT_CLASS}
              value={brief.name}
              onChange={(event) => setBrief({ ...brief, name: event.target.value })}
            />
          </Field>
          <Field label="Чем занимается команда" hint="какие сервисы и системы ведёт">
            <textarea
              maxLength={3000}
              rows={4}
              placeholder={SERVICES_HINT}
              className={TEXTAREA_CLASS}
              value={brief.services}
              onChange={(event) => setBrief({ ...brief, services: event.target.value })}
            />
          </Field>
          <Field label="Продукты и системы" hint="новости о них пойдут первыми" isGroup>
            <ChipsInput
              label="Продукты и системы"
              placeholder="MaxPatrol SIEM, Cisco ASA, Siemens S7…"
              values={brief.systems}
              max={20}
              onChange={(systems) => setBrief({ ...brief, systems })}
            />
          </Field>

          {(!spec || isStale) && (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type={spec ? 'button' : 'submit'}
                onClick={spec ? pick : undefined}
                variant={spec ? 'secondary' : 'primary'}
                icon={spec ? <RefreshCw size={15} /> : <Sparkles size={15} />}
                isBusy={draft.isPending}
                disabled={isNameShort}
              >
                {spec ? 'Подобрать заново' : 'Подобрать интересы'}
              </Button>
              <span aria-live="polite" className="text-sm text-muted">
                {draft.isPending
                  ? 'Читаем описание, обычно это занимает до полуминуты'
                  : isStale
                    ? 'Описание изменилось после подбора: темы можно подобрать заново или оставить.'
                    : null}
              </span>
            </div>
          )}
          <ErrorNote error={draft.error} />

          <AnimatePresence initial={false}>
            {spec && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="space-y-2"
              >
                <SpecReview
                  spec={spec}
                  onChange={setSpec}
                  title="Профиль сотрудников"
                  draftedBy={draftedBy}
                />
                <p className="px-1 text-xs text-muted">
                  Отдельным людям или ролям в команде профиль можно поменять потом. Руководителям по
                  должности достаётся краткий брифинг вместо карточек.
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          <ErrorNote error={save.error} />
          <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
            <Button disabled={save.isPending} onClick={() => onOpenChange(false)}>
              Отмена
            </Button>
            <Button
              variant="primary"
              disabled={!canSave || draft.isPending}
              isBusy={save.isPending}
              onClick={submit}
            >
              {team ? 'Сохранить' : 'Создать команду'}
            </Button>
          </div>
          {team && team.members.length > 0 && (
            <p className="text-right text-xs text-muted">
              Изменения получат сотрудники, которые не правили профиль сами.
            </p>
          )}
        </form>
      </DialogContent>
    </Dialog>
  )
}
