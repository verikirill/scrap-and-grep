import { useState } from 'react'
import { INPUT_CLASS, TEXTAREA_CLASS } from '../../components/tokens'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { Company } from '../../lib/company'
import { useUpdateCompany } from '../../lib/companyQueries'
import { toast } from '../../lib/toast'
import { LogoPicker } from './CompanyLogo'

/** The company's name and what it does: the second is read with every team's description. */
export function CompanyDialog({ company, onClose }: { company: Company; onClose: () => void }) {
  const update = useUpdateCompany()
  const [name, setName] = useState(company.name)
  const [about, setAbout] = useState(company.about)

  return (
    <Dialog open onOpenChange={(open) => !open && !update.isPending && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>О компании</DialogTitle>
          <DialogDescription>
            Логотип увидят сотрудники, а описание сервис учитывает, когда подбирает темы для команд.
          </DialogDescription>
        </DialogHeader>
        <LogoPicker name={company.name} logoUrl={company.logo_url} />
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            update.mutate(
              { name: name.trim(), about: about.trim() },
              {
                onSuccess: () => {
                  toast.success('Сохранено')
                  onClose()
                },
              },
            )
          }}
        >
          <Field label="Название компании">
            <input
              required
              minLength={2}
              maxLength={120}
              className={INPUT_CLASS}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Чем занимается компания">
            <textarea
              maxLength={2000}
              rows={4}
              className={TEXTAREA_CLASS}
              value={about}
              onChange={(event) => setAbout(event.target.value)}
            />
          </Field>
          <ErrorNote error={update.error} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button disabled={update.isPending} onClick={onClose}>
              Отмена
            </Button>
            <Button
              type="submit"
              variant="primary"
              isBusy={update.isPending}
              disabled={name.trim().length < 2}
            >
              Сохранить
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
