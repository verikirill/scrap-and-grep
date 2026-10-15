import { useRef, useState } from 'react'
import { toast } from '../../lib/toast'
import { Check, ContentCopy, Link2, LinkOff, Share } from '../../components/icons'
import { INPUT_CLASS } from '../../components/tokens'
import { Button, ErrorNote } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { Profile } from '../../lib/api'
import { useProfileLink } from '../../lib/queries'
import { ProfileAvatar } from './ProfileLook'

const COPIED_MS = 2000

function shareUrl(token: string): string {
  return `${window.location.origin}/share/${token}`
}

/** The owner's side: make a link to the profile, copy or send it, close it. */
export function ShareProfileButton({ profile }: { profile: Profile }) {
  const [isOpen, setOpen] = useState(false)
  const [isCopied, setCopied] = useState(false)
  const field = useRef<HTMLInputElement>(null)
  const link = useProfileLink()
  const url = profile.share_token ? shareUrl(profile.share_token) : null
  const canSend = typeof navigator.share === 'function'

  const copy = async () => {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), COPIED_MS)
      toast.success('Ссылка скопирована')
    } catch {
      // No clipboard outside HTTPS: leave the link selected for Ctrl+C.
      field.current?.select()
      toast('Ссылка выделена, скопируйте её')
    }
  }

  const send = async () => {
    if (!url) return
    try {
      await navigator.share({
        title: profile.spec.name,
        text: 'Профиль интересов в Scrap&Grep',
        url,
      })
    } catch {
      // Closing the system sheet is not an error worth showing.
    }
  }

  return (
    <>
      <Button size="sm" variant="ghost" icon={<Share size={15} />} onClick={() => setOpen(true)}>
        Поделиться
      </Button>
      <Dialog
        open={isOpen}
        onOpenChange={(next) => {
          // Only closing comes through here (the button opens the dialog by
          // itself), so the last visit's error is forgotten on the way out.
          if (!next) link.reset()
          setCopied(false)
          setOpen(next)
        }}
      >
        <DialogContent className="max-h-[calc(100dvh-2rem)] gap-5 overflow-x-hidden overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">Поделиться профилем</DialogTitle>
            <DialogDescription>
              По ссылке откроется карточка профиля: название, роль, интересы и исключения.
              Получатель сможет добавить копию себе. Ваши выпуски, отметки и резюме останутся
              скрыты.
            </DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-3 rounded-2xl bg-surface-secondary p-3">
            <ProfileAvatar profile={profile} size={40} />
            <p className="min-w-0 flex-1 truncate font-medium">{profile.spec.name}</p>
          </div>

          {url ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  ref={field}
                  readOnly
                  value={url}
                  aria-label="Ссылка на профиль"
                  onFocus={(event) => event.currentTarget.select()}
                  className={`${INPUT_CLASS} min-w-0 font-mono text-xs`}
                />
                <Button
                  variant="primary"
                  icon={isCopied ? <Check size={16} /> : <ContentCopy size={16} />}
                  onClick={() => void copy()}
                  className="shrink-0"
                >
                  {isCopied ? 'Скопировано' : 'Копировать'}
                </Button>
              </div>
              <p className="text-xs text-muted">
                Ссылка показывает профиль в актуальном виде на момент открытия. Добавленные копии
                останутся у получателей, даже если вы закроете доступ.
              </p>
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  variant="danger"
                  icon={<LinkOff size={16} />}
                  isBusy={link.isPending}
                  onClick={() => link.mutate({ id: profile.id, isShared: false })}
                >
                  Закрыть доступ
                </Button>
                {canSend && (
                  <Button variant="tonal" icon={<Share size={16} />} onClick={() => void send()}>
                    Отправить
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex justify-end">
              <Button
                variant="primary"
                icon={<Link2 size={16} />}
                isBusy={link.isPending}
                onClick={() => link.mutate({ id: profile.id, isShared: true })}
              >
                Создать ссылку
              </Button>
            </div>
          )}
          <ErrorNote error={link.error} />
        </DialogContent>
      </Dialog>
    </>
  )
}
