import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { CircleCheck, LibraryAdd, LinkOff } from '../../components/icons'
import { Button, ErrorNote } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { SharedProfile } from '../../lib/api'
import { useAcceptSharedProfile, useSharedProfile } from '../../lib/queries'
import { ProfileAvatar } from './ProfileLook'

const LANGUAGES: Record<string, string> = { ru: 'русский', en: 'английский' }

function Loading() {
  return (
    <div className="space-y-4" aria-busy>
      <DialogTitle className="sr-only">Профиль по ссылке</DialogTitle>
      <DialogDescription className="sr-only">
        Загружаем профиль, которым с вами поделились.
      </DialogDescription>
      <div className="flex items-center gap-3">
        <div className="skeleton size-14 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-3 w-32" />
          <div className="skeleton h-5 w-48" />
        </div>
      </div>
      <div className="skeleton h-16" />
      <div className="skeleton h-10" />
    </div>
  )
}

function Gone({ error, onClose }: { error: unknown; onClose: () => void }) {
  return (
    <div className="space-y-4">
      <DialogHeader>
        <span className="grid size-12 place-items-center rounded-full bg-error-container text-on-error-container">
          <LinkOff size={24} />
        </span>
        <DialogTitle className="text-lg">Профиль не открылся</DialogTitle>
        <DialogDescription>
          {error instanceof Error ? error.message : 'Ссылка не работает.'}
        </DialogDescription>
      </DialogHeader>
      <div className="flex justify-end">
        <Button variant="primary" onClick={onClose}>
          Понятно
        </Button>
      </div>
    </div>
  )
}

function Chips({ items, tone }: { items: readonly string[]; tone: 'interest' | 'exclusion' }) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li
          key={item}
          className={
            tone === 'interest'
              ? 'rounded-lg bg-secondary-container px-2.5 py-1 text-xs font-medium text-on-secondary-container'
              : 'rounded-lg border border-outline-variant px-2.5 py-1 text-xs text-on-surface-variant'
          }
        >
          {item}
        </li>
      ))}
    </ul>
  )
}

function Preview({
  shared,
  isAdding,
  error,
  onAdd,
  onOpen,
  onDecline,
}: {
  shared: SharedProfile
  isAdding: boolean
  error: unknown
  onAdd: () => void
  onOpen: (id: string) => void
  onDecline: () => void
}) {
  const { spec } = shared
  const languages = spec.languages.map((code) => LANGUAGES[code] ?? code).join(' и ')
  return (
    <div className="space-y-5">
      <DialogHeader className="gap-3">
        <div className="flex items-center gap-3.5">
          <ProfileAvatar profile={shared} size={56} />
          <div className="min-w-0">
            <p className="text-xs font-medium text-on-surface-variant">Вам прислали профиль</p>
            <DialogTitle className="mt-1 text-xl leading-tight break-words">
              {spec.name}
            </DialogTitle>
          </div>
        </div>
        <DialogDescription className="line-clamp-4 text-sm">
          {spec.role || 'Роль не описана, профиль задан только интересами.'}
        </DialogDescription>
      </DialogHeader>

      <section className="space-y-2">
        <h3 className="text-xs font-medium text-on-surface-variant">
          Интересы, {spec.interests.length}
        </h3>
        <Chips items={spec.interests.map((interest) => interest.title)} tone="interest" />
      </section>
      {spec.exclusions.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium text-on-surface-variant">Не показывать</h3>
          <Chips items={spec.exclusions} tone="exclusion" />
        </section>
      )}
      <p className="text-xs text-on-surface-variant">
        Языки: {languages}. До {spec.max_items} публикаций в выпуске.
      </p>

      {shared.own_id ? (
        <p className="flex items-center gap-2 rounded-xl bg-surface-container px-3.5 py-2.5 text-sm">
          <CircleCheck size={18} className="shrink-0 text-primary" filled />
          Такой профиль уже есть у вас.
        </p>
      ) : (
        <p className="text-sm text-on-surface-variant">
          Добавится ваша копия. Её можно менять как угодно, у отправителя ничего не изменится.
        </p>
      )}
      <ErrorNote error={error} />

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="ghost" onClick={onDecline} disabled={isAdding}>
          {shared.own_id ? 'Закрыть' : 'Отклонить'}
        </Button>
        {shared.own_id ? (
          <Button variant="primary" onClick={() => onOpen(shared.own_id as string)}>
            Открыть профиль
          </Button>
        ) : (
          <Button
            variant="primary"
            icon={<LibraryAdd size={16} />}
            isBusy={isAdding}
            onClick={onAdd}
            autoFocus
          >
            Добавить себе
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * The recipient's side: what the link holds, and the choice to take it or
 * not. Either way the dialog leaves for the digest page, with the new profile
 * picked when it was taken.
 */
export function SharedProfileDialog({ token }: { token: string }) {
  const navigate = useNavigate()
  const shared = useSharedProfile(token)
  const accept = useAcceptSharedProfile()
  const leave = (profileId?: string) =>
    navigate(profileId ? `/?profile=${profileId}` : '/', { replace: true })

  return (
    // While the copy is being made the dialog stays: its answer picks the new profile.
    <Dialog open onOpenChange={(open) => !open && !accept.isPending && leave()}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] overflow-x-hidden overflow-y-auto rounded-[28px] p-6 sm:max-w-md"
        showCloseButton={false}
      >
        {shared.isPending ? (
          <Loading />
        ) : shared.isError ? (
          <Gone error={shared.error} onClose={() => leave()} />
        ) : (
          <Preview
            shared={shared.data}
            isAdding={accept.isPending}
            error={accept.error}
            onDecline={() => leave()}
            onOpen={(id) => leave(id)}
            onAdd={() =>
              accept.mutate(token, {
                onSuccess: (profile) => {
                  toast.success(`Профиль «${profile.spec.name}» добавлен`)
                  leave(profile.id)
                },
              })
            }
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
