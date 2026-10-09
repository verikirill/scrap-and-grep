import { useState } from 'react'
import type { FormEvent } from 'react'
import { toast } from '../../lib/toast'
import { Send } from '../../components/icons'
import { INPUT_CLASS } from '../../components/tokens'
import { Button, ErrorNote, Field } from '../../components/ui'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import type { Digest } from '../../lib/api'
import { useMailDigest, useMailState } from '../../lib/queries'

/**
 * A finished digest sent by email: the text of the Markdown export as a
 * letter, the DOCX attached. Shown only on a server with a mail server set.
 */
export function MailButton({ digest }: { digest: Digest }) {
  const isDone = digest.status === 'done'
  const state = useMailState(digest.id, isDone)
  const send = useMailDigest(digest.id)
  const [isOpen, setOpen] = useState(false)
  const [address, setAddress] = useState<string | null>(null)
  if (!isDone || state.data?.available !== true) return null

  const { default_to: own, domains } = state.data
  const to = address ?? own ?? ''
  const hint = domains.length > 0 ? `только ${domains.join(', ')}` : undefined

  const submit = (event: FormEvent) => {
    event.preventDefault()
    send.mutate(to.trim() || null, {
      onSuccess: (sent) => {
        toast.success(`Выпуск отправлен на ${sent.to}`)
        setOpen(false)
      },
    })
  }

  return (
    <>
      <Button variant="secondary" size="sm" icon={<Send size={15} />} onClick={() => setOpen(true)}>
        На почту
      </Button>
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          setOpen(open)
          if (!open) send.reset()
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">Выпуск на почту</DialogTitle>
            <DialogDescription>
              Письмо с текстом выпуска, ссылками на источники и DOCX во вложении.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Кому" hint={hint}>
              <input
                type="email"
                value={to}
                onChange={(event) => setAddress(event.target.value)}
                placeholder="analyst@company.ru"
                autoComplete="email"
                required
                className={INPUT_CLASS}
              />
            </Field>
            <ErrorNote error={send.error} />
            <div className="flex justify-end">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                icon={<Send size={15} />}
                isBusy={send.isPending}
              >
                Отправить
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
