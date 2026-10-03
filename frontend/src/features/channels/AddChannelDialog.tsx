import { Plus } from '../../components/icons'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button, ErrorNote, Field } from '../../components/ui'
import { SelectField } from '../../components/SelectField'
import { INPUT_CLASS } from '../../components/tokens'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import { useAddChannel, useBots } from '../../lib/publishingQueries'
import { useProfiles } from '../../lib/queries'

/** Connect a channel: which bot posts, where, and for which audience. */
export function AddChannelDialog() {
  const [open, setOpen] = useState(false)
  const { data: bots } = useBots()
  const { data: profiles } = useProfiles()
  const add = useAddChannel()
  const [botId, setBotId] = useState('')
  const [chat, setChat] = useState('')
  const [profileId, setProfileId] = useState('')
  const bot = botId || bots?.[0]?.id || ''
  const profile = profileId || profiles?.[0]?.id || ''

  return (
    <>
      <div className="flex flex-col items-end gap-1">
        <Button
          variant="primary"
          icon={<Plus size={18} />}
          disabled={!bots?.length}
          onClick={() => setOpen(true)}
        >
          Добавить канал
        </Button>
        {/* A disabled button says why next to it, not in a tooltip a phone never shows. */}
        {bots?.length === 0 && (
          <span className="text-xs text-muted-foreground">Сначала подключите бота</span>
        )}
      </div>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          // A refusal from the last attempt is not this attempt's.
          if (next) add.reset()
          setOpen(next)
        }}
      >
        <DialogContent className="rounded-[28px] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Новый канал</DialogTitle>
            <DialogDescription>
              Добавьте бота в канал администратором с правом публиковать сообщения, затем укажите
              канал здесь.
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              add.mutate(
                { botId: bot, chat, profileId: profile || null },
                {
                  onSuccess: (channel) => {
                    toast.success(`Канал «${channel.title}» подключён`)
                    setOpen(false)
                    setChat('')
                  },
                },
              )
            }}
          >
            <Field label="Бот">
              <SelectField
                label="Бот"
                value={bot}
                onChange={setBotId}
                options={(bots ?? []).map((item) => ({
                  value: item.id,
                  label: `@${item.username}`,
                }))}
              />
            </Field>
            <Field label="Канал" hint="@имя, t.me/имя или -100…">
              <input
                value={chat}
                onChange={(event) => setChat(event.target.value)}
                placeholder="@my_channel"
                className={INPUT_CLASS}
                autoFocus
              />
            </Field>
            <Field label="Аудитория" hint="по чьему профилю отбирать новости">
              <SelectField
                label="Аудитория"
                value={profile}
                onChange={setProfileId}
                options={(profiles ?? []).map((item) => ({
                  value: item.id,
                  label: item.spec.name,
                }))}
              />
            </Field>
            <ErrorNote error={add.error} />
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Отмена
              </Button>
              <Button
                type="submit"
                variant="primary"
                isBusy={add.isPending}
                disabled={!chat.trim() || !bot}
              >
                Подключить
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
