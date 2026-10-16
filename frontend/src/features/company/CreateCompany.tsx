import { useState } from 'react'
import { Link2 as LinkIcon, Sparkles, Users } from '../../components/icons'
import { INPUT_CLASS, TEXTAREA_CLASS } from '../../components/tokens'
import { Button, Card, ErrorNote, Field, IconTile } from '../../components/ui'
import { useCreateCompany } from '../../lib/companyQueries'

const STEPS = [
  {
    icon: Users,
    title: 'Опишите команды',
    text: 'Чем занимается каждая команда и какие сервисы и системы ведёт.',
  },
  {
    icon: Sparkles,
    title: 'Проверьте подобранные темы',
    text: 'Сервис сам подберёт команде роль и темы новостей, а вы уберёте лишнее.',
  },
  {
    icon: LinkIcon,
    title: 'Вставьте список сотрудников',
    text: 'Каждый получит аккаунт с готовым профилем и ссылку, по которой задаст пароль.',
  },
]

/** The first screen of the section: what a company space gives and the form that makes one. */
export function CreateCompany() {
  const create = useCreateCompany()
  const [name, setName] = useState('')
  const [about, setAbout] = useState('')

  return (
    <Card className="grid gap-8 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <div>
        <IconTile icon={<Users />} className="mb-5" />
        <h2 className="text-xl font-semibold tracking-tight">Пространство компании</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Заведите команды один раз, и сотрудникам не придётся ничего настраивать: каждый войдёт в
          сервис с профилем интересов под работу своей команды.
        </p>
        <form
          className="mt-6 max-w-xl space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            create.mutate({ name: name.trim(), about: about.trim() })
          }}
        >
          <Field label="Название компании">
            <input
              required
              minLength={2}
              maxLength={120}
              placeholder="АО «Энергосеть»"
              className={INPUT_CLASS}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Чем занимается компания" hint="необязательно">
            <textarea
              maxLength={2000}
              rows={3}
              placeholder="Распределение электроэнергии в трёх регионах, 40 подстанций, собственный ЦОД."
              className={TEXTAREA_CLASS}
              value={about}
              onChange={(event) => setAbout(event.target.value)}
            />
          </Field>
          <p className="px-1 text-xs text-muted">
            Описание помогает точнее подобрать темы: сервис читает его вместе с описанием каждой
            команды.
          </p>
          <ErrorNote error={create.error} />
          <Button
            type="submit"
            variant="cta"
            isBusy={create.isPending}
            disabled={name.trim().length < 2}
          >
            Создать пространство
          </Button>
        </form>
      </div>
      <ol className="space-y-3 self-start rounded-3xl bg-surface-secondary p-4 sm:p-5">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex gap-3">
            <span
              aria-hidden
              className="grid size-9 shrink-0 place-items-center rounded-2xl bg-surface text-accent"
            >
              <step.icon size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold">
                <span className="text-muted">{index + 1}. </span>
                {step.title}
              </p>
              <p className="mt-0.5 text-sm text-muted">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}
