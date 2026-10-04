import { Bot as BotIcon, KeyRound, Trash2 } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button, Card, Chip, ErrorNote } from '../../components/ui'
import { INPUT_CLASS, rowMotion } from '../../components/tokens'
import { useAddBot, useBots, useDeleteBot } from '../../lib/publishingQueries'

/** The bots a reader connected: one bot can post to many channels. */
export function BotsPanel() {
  const { data: bots, isPending } = useBots()
  const add = useAddBot()
  const remove = useDeleteBot()
  const [token, setToken] = useState('')

  const submit = () =>
    add.mutate(token, {
      onSuccess: (bot) => {
        setToken('')
        toast.success(`Бот @${bot.username} подключён`)
      },
    })

  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-base font-medium">
        <BotIcon size={18} className="text-primary" /> Боты
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Создайте бота через @BotFather и вставьте его токен. Токен хранится в зашифрованном виде и
        больше не показывается.
      </p>

      <ul className="mt-4 space-y-2">
        {isPending && <li className="skeleton h-14" />}
        <AnimatePresence initial={false}>
          {bots?.map((bot, index) => (
            <motion.li
              key={bot.id}
              {...rowMotion(index)}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-3 rounded-2xl bg-surface-container px-3 py-2.5"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-tertiary-container text-on-tertiary-container">
                <BotIcon size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">@{bot.username}</span>
                <span className="block truncate text-xs text-outline">
                  {bot.token_hint} · каналов: {bot.channels}
                </span>
              </span>
              {bot.status !== 'ok' && <Chip tone="danger">ошибка</Chip>}
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Отключить @${bot.username}`}
                icon={<Trash2 size={15} />}
                isBusy={remove.isPending && remove.variables === bot.id}
                onClick={() => {
                  if (window.confirm(`Отключить @${bot.username} и все его каналы?`))
                    remove.mutate(bot.id)
                }}
              />
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <input
          type="password"
          autoComplete="off"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="123456789:AA…"
          aria-label="Токен бота"
          className={INPUT_CLASS}
        />
        <Button
          type="submit"
          variant="tonal"
          icon={<KeyRound size={16} />}
          isBusy={add.isPending}
          disabled={token.trim().length < 20}
        >
          Подключить
        </Button>
      </form>
      <div className="mt-2">
        <ErrorNote error={add.error} />
      </div>
    </Card>
  )
}
