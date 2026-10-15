import { toast } from '../lib/toast'
import { Camera, LogOut, ShieldCheck, Trash2 } from '../components/icons'
import { useRef, useState } from 'react'
import { UserAvatar } from '../components/UserAvatar'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { INPUT_CLASS, buttonClass } from '../components/tokens'
import { Loading, PageSkeleton, Skeleton } from '../components/loading'
import { Button, Card, Chip, ErrorNote, Field, PageHeader } from '../components/ui'
import { AvatarPicker } from '../features/account/AvatarPicker'
import { McpAccess } from '../features/account/McpAccess'
import { ResumeDrop } from '../features/resume/ResumeDrop'
import { ResumeFactsView } from '../features/resume/ResumeFactsView'
import { ResumeProcessing } from '../features/resume/ResumeProcessing'
import type { Me } from '../lib/api'
import { ONBOARDING_PATH } from '../lib/onboarding'
import { useMediaQuery } from '../lib/useMediaQuery'
import {
  isResumeStuck,
  useAvatar,
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
    <Card className="p-5 sm:p-6">
      <h2 className="text-base font-semibold">Резюме</h2>
      <p className="mt-1 mb-4 text-sm text-muted">
        Резюме задаёт специализацию, и лента учитывает её наравне с интересами.
      </p>

      {resume.isPending ? (
        <Loading label="Загружаем резюме" className="space-y-3">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-3.5 w-2/3" />
        </Loading>
      ) : isProcessing ? (
        <ResumeProcessing
          usesModel={meta.data?.llm_provider === 'ollama'}
          usesDocling={meta.data?.resume_parser === 'docling'}
        />
      ) : (
        <div className="space-y-4">
          {current?.status === 'ready' && current.facts && (
            <div className="rounded-xl bg-surface-secondary p-4 sm:p-5">
              <ResumeFactsView resume={current} facts={current.facts} skillsShown={14} />
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/welcome" className={buttonClass('secondary', 'sm')}>
                  Создать профиль по резюме
                </Link>
                <Button
                  size="sm"
                  variant="danger"
                  icon={<Trash2 size={14} />}
                  isBusy={remove.isPending}
                  onClick={() => {
                    if (window.confirm('Удалить все данные из резюме?')) remove.mutate()
                  }}
                >
                  Удалить данные
                </Button>
              </div>
            </div>
          )}
          {isStuck && (
            <p role="alert" className="rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
              Резюме разбирается дольше обычного. Попробуйте загрузить файл ещё раз.
            </p>
          )}
          {current?.status === 'failed' && (
            <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {current.error}
            </p>
          )}
          <ResumeDrop
            meta={meta.data}
            isBusy={upload.isPending}
            onFile={(file) => upload.mutate(file)}
            isCompact={current?.status === 'ready'}
          />
          <ErrorNote error={upload.error ?? remove.error ?? resume.error} />
          <p className="flex items-start gap-2 text-xs text-muted">
            <ShieldCheck size={15} className="mt-px shrink-0 text-success" />
            Файл удаляется сразу после разбора. Имя и контакты стираются до анализа. Сохраняются
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

  // Everyone who presses the button on the sign-in page lands here: nobody
  // may take the account away from the others (the server refuses too).
  if (me.is_shared) {
    return (
      <Card className="p-5">
        <h2 className="text-base font-semibold">Общий аккаунт</h2>
        <p className="mt-1 text-sm text-muted">
          В этот аккаунт входят без пароля все, кто нажал кнопку на странице входа, поэтому удалить
          его нельзя. Изменения в профилях и выпусках увидят и другие. Чтобы настроить всё под себя,
          выйдите и зарегистрируйтесь.
        </p>
      </Card>
    )
  }

  // A guest has no password to confirm with and nothing worth keeping.
  if (me.is_demo) {
    return (
      <Card className="p-5">
        <h2 className="text-base font-semibold">Временный аккаунт</h2>
        <p className="mt-1 text-sm text-muted">
          Временный аккаунт и все данные удалятся через сутки. Чтобы сохранить настройки,
          зарегистрируйтесь.
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
            Удалить аккаунт
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
    <Card className="p-5">
      <h2 className="text-base font-semibold">Удаление аккаунта</h2>
      <p className="mt-1 text-sm text-muted">
        Вместе с аккаунтом безвозвратно удалятся все профили, выпуски, данные резюме и отметки.
      </p>
      {isOpen ? (
        <form onSubmit={submit} className="mt-4 max-w-sm space-y-3">
          <Field label="Пароль для подтверждения">
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

/** The first-run introduction, again: it changes nothing until a step is taken. */
function Introduction() {
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold">Знакомство с сервисом</h2>
      <p className="mt-1 text-sm text-muted">
        Три коротких шага: что умеет сервис, профиль интересов и первый выпуск.
      </p>
      <div className="mt-4">
        <Link to={ONBOARDING_PATH} className={buttonClass('secondary', 'sm')}>
          Пройти знакомство ещё раз
        </Link>
      </div>
    </Card>
  )
}

const AVATAR_TYPES = 'image/jpeg,image/png,image/webp,image/gif'
const AVATAR_MAX_BYTES = 5_000_000

/** A guest's and a shared account's addresses are made up: they say nothing to the reader. */
function accountLine(me: Me): string {
  if (me.is_shared) return 'Общий аккаунт без пароля'
  return me.is_demo ? 'Без почты и пароля' : me.email
}

/** Who is signed in, with their picture: a photo of their own or one of the ready ones. */
function Identity({ me }: { me: Me }) {
  const { upload, pick, remove } = useAvatar()
  const input = useRef<HTMLInputElement>(null)
  const isBusy = upload.isPending || pick.isPending || remove.isPending
  const take = (file: File | undefined) => {
    if (!file) return
    // The server checks the content; this only saves a pointless upload.
    if (file.size > AVATAR_MAX_BYTES) {
      toast.error('Размер файла превышает 5 МБ. Выберите изображение поменьше.')
      return
    }
    upload.mutate(file, { onSuccess: () => toast.success('Фото обновлено') })
  }

  return (
    <Card className="flex flex-col items-center p-5 text-center">
      <button
        type="button"
        disabled={isBusy}
        onClick={() => input.current?.click()}
        aria-label={me.avatar_url ? 'Сменить фото' : 'Загрузить фото'}
        className="group relative rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:opacity-70"
      >
        <UserAvatar me={me} size={96} />
        <span className="absolute right-0 bottom-0 grid size-8 place-items-center rounded-full bg-accent text-accent-foreground shadow-overlay transition-transform duration-300 group-hover:scale-110">
          <Camera size={16} />
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept={AVATAR_TYPES}
        hidden
        onChange={(event) => {
          take(event.target.files?.[0])
          // The same file may be picked again after an error.
          event.target.value = ''
        }}
      />
      <p className="mt-3 max-w-full truncate text-base font-semibold">{me.display_name}</p>
      <p className="max-w-full truncate text-sm text-muted">{accountLine(me)}</p>
      {(me.is_demo || me.is_shared || me.is_admin) && (
        <div className="mt-2 flex flex-wrap justify-center gap-1.5">
          {me.is_demo && <Chip tone="spark">временный</Chip>}
          {me.is_shared && <Chip tone="spark">общий</Chip>}
          {me.is_admin && <Chip tone="accent">администратор</Chip>}
        </div>
      )}
      <AvatarPicker
        me={me}
        isDisabled={isBusy}
        onUpload={() => input.current?.click()}
        onPick={(preset) =>
          pick.mutate(preset, { onSuccess: () => toast.success('Картинка обновлена') })
        }
      />
      {me.avatar_url && (
        <Button
          size="sm"
          variant="ghost"
          className="mt-2"
          isBusy={remove.isPending}
          onClick={() => remove.mutate(undefined, { onSuccess: () => toast('Фото убрано') })}
        >
          Удалить фото
        </Button>
      )}
      <p className="mt-2 text-xs text-muted">
        Своё фото: JPEG, PNG, WebP или GIF до 5 МБ. Кадрируем до квадрата и очистим от метаданных
        съёмки.
      </p>
      <div className="mt-2 w-full">
        <ErrorNote error={upload.error ?? pick.error ?? remove.error} />
      </div>
    </Card>
  )
}

export function AccountPage() {
  const me = useMe()
  const { logout } = useSignOut()
  const isWide = useMediaQuery('(min-width: 1024px)')
  const user = me.data
  if (!user) return <PageSkeleton label="Открываем аккаунт" />

  return (
    <>
      <PageHeader
        title="Аккаунт"
        actions={
          <Button
            icon={<LogOut size={15} />}
            isBusy={logout.isPending}
            onClick={() => {
              // A temporary account has no password: once left, it cannot be opened again.
              const isSure =
                !user.is_demo ||
                window.confirm(
                  'Войти во временный аккаунт повторно нельзя, поэтому все профили, выпуски и отметки будут потеряны. Выйти?',
                )
              if (isSure) logout.mutate()
            }}
          >
            Выйти
          </Button>
        }
      />
      <ErrorNote error={logout.error} />
      {/* Who and what to do with the account on the left, the bulky parts on the right. */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)] lg:items-start">
        <aside className="space-y-5 lg:sticky lg:top-9">
          <Identity me={user} />
          <Introduction />
          {isWide && <DangerZone me={user} />}
        </aside>
        <div className="min-w-0 space-y-5">
          <ResumeSection />
          <McpAccess />
          {/* On a phone the column order is the reading order: removal comes last. */}
          {!isWide && <DangerZone me={user} />}
        </div>
      </div>
    </>
  )
}
