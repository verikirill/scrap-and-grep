import clsx from 'clsx'
import { LogOut, ShieldCheck, Trash2 } from '../components/icons'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { INPUT_CLASS, buttonClass } from '../components/tokens'
import { Button, Card, Chip, ErrorNote, Field, PageHeader } from '../components/ui'
import { McpAccess } from '../features/account/McpAccess'
import { ResumeDrop } from '../features/resume/ResumeDrop'
import { ResumeFactsView } from '../features/resume/ResumeFactsView'
import { ResumeProcessing } from '../features/resume/ResumeProcessing'
import type { Me } from '../lib/api'
import {
  isResumeStuck,
  useMe,
  useMeta,
  useResume,
  useResumeMutations,
  useSignOut,
} from '../lib/queries'

function ResumeSection() {
  const meta = useMeta()
  const resume = useResume()
  const { upload, remove } = useResumeMutations()
  const current = resume.data
  const isStuck = isResumeStuck(current)
  const isProcessing = upload.isPending || (current?.status === 'processing' && !isStuck)

  return (
    <Card className="p-6">
      <h2 className="text-base font-semibold">Резюме</h2>
      <p className="mt-1 mb-5 text-sm text-muted-foreground">
        По резюме определяется специализация. Она участвует в ленте наравне с интересами.
      </p>

      {isProcessing ? (
        <ResumeProcessing
          usesModel={meta.data?.llm_provider === 'ollama'}
          usesDocling={meta.data?.resume_parser === 'docling'}
        />
      ) : (
        <div className="space-y-5">
          {current?.status === 'ready' && current.facts && (
            <div className="rounded-xl bg-surface-container p-5">
              <ResumeFactsView resume={current} facts={current.facts} />
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/welcome" className={buttonClass('secondary', 'sm')}>
                  Собрать профиль из резюме
                </Link>
                <Button
                  size="sm"
                  variant="danger"
                  icon={<Trash2 size={14} />}
                  isBusy={remove.isPending}
                  onClick={() => {
                    if (window.confirm('Стереть всё, что известно из резюме?')) remove.mutate()
                  }}
                >
                  Стереть
                </Button>
              </div>
            </div>
          )}
          {isStuck && (
            <p role="alert" className="rounded-lg bg-spark-container px-3 py-2 text-sm text-spark">
              Резюме разбирается дольше обычного. Попробуйте загрузить файл ещё раз.
            </p>
          )}
          {current?.status === 'failed' && (
            <p
              role="alert"
              className="rounded-lg bg-error-container px-3 py-2 text-sm text-destructive"
            >
              {current.error}
            </p>
          )}
          <ResumeDrop
            meta={meta.data}
            isBusy={upload.isPending}
            onFile={(file) => upload.mutate(file)}
          />
          <ErrorNote error={upload.error ?? remove.error ?? resume.error} />
          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck size={15} className="mt-px shrink-0 text-success" />
            Файл удаляется сразу после разбора. Имя и контакты вырезаются до анализа; хранятся
            только должность, навыки и предложенные темы.
          </p>
        </div>
      )}
    </Card>
  )
}

function DangerZone({ me }: { me: Me }) {
  const { deleteAccount } = useSignOut()
  const [password, setPassword] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  // A guest has no password to confirm with and nothing worth keeping.
  if (me.is_demo) {
    return (
      <Card className="p-6">
        <h2 className="text-base font-semibold">Временный аккаунт</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Он удалится сам через сутки вместе со всем, что вы в нём сделали. Чтобы сохранить
          настройки, заведите постоянный аккаунт.
        </p>
        <ErrorNote error={deleteAccount.error} />
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/register" className={buttonClass('primary', 'sm')}>
            Зарегистрироваться
          </Link>
          <Button
            size="sm"
            variant="danger"
            icon={<Trash2 size={14} />}
            isBusy={deleteAccount.isPending}
            onClick={() => deleteAccount.mutate('')}
          >
            Удалить сейчас
          </Button>
        </div>
      </Card>
    )
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    deleteAccount.mutate(password)
  }

  return (
    <Card className="p-6">
      <h2 className="text-base font-semibold">Удаление аккаунта</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Вместе с аккаунтом удаляются профили, выпуски, данные резюме и все оценки. Восстановить их
        будет нельзя.
      </p>
      {isOpen ? (
        <form onSubmit={submit} className="mt-4 max-w-sm space-y-3">
          <Field label="Пароль, чтобы подтвердить">
            <input
              required
              type="password"
              autoComplete="current-password"
              maxLength={128}
              className={INPUT_CLASS}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <ErrorNote error={deleteAccount.error} />
          <div className="flex gap-2">
            <Button type="submit" variant="danger" isBusy={deleteAccount.isPending}>
              Удалить навсегда
            </Button>
            <Button variant="ghost" onClick={() => setIsOpen(false)}>
              Отмена
            </Button>
          </div>
        </form>
      ) : (
        <Button
          className="mt-4"
          variant="danger"
          icon={<Trash2 size={15} />}
          onClick={() => setIsOpen(true)}
        >
          Удалить аккаунт
        </Button>
      )}
    </Card>
  )
}

export function AccountPage() {
  const me = useMe()
  const { logout } = useSignOut()
  const user = me.data
  if (!user) return null

  return (
    <>
      <PageHeader
        title="Аккаунт"
        actions={
          <Button
            icon={<LogOut size={15} />}
            isBusy={logout.isPending}
            onClick={() => logout.mutate()}
          >
            Выйти
          </Button>
        }
      />
      <div className="max-w-3xl space-y-5">
        <Card className="flex items-center gap-4 p-6">
          <span
            aria-hidden
            className={clsx(
              'grid size-12 shrink-0 place-items-center rounded-2xl text-lg font-semibold',
              'bg-primary-container text-on-primary-container',
            )}
          >
            {user.display_name.slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold">{user.display_name}</p>
            <p className="truncate text-sm text-muted-foreground">
              {/* A guest's address is made up: it says nothing to the reader. */}
              {user.is_demo ? 'Гостевой вход, без почты и пароля' : user.email}
            </p>
          </div>
          <div className="ml-auto flex flex-wrap justify-end gap-1.5">
            {user.is_demo && <Chip tone="spark">временный</Chip>}
            {user.is_admin && <Chip tone="accent">администратор</Chip>}
          </div>
        </Card>
        <ErrorNote error={logout.error} />
        <ResumeSection />
        <McpAccess />
        <DangerZone me={user} />
      </div>
    </>
  )
}
