import clsx from 'clsx'
import {
  CalendarClock,
  FilePen,
  Send,
  Settings2,
  Trash2,
  TriangleAlert,
} from '../../components/icons'
import { motion } from 'motion/react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button, Card, Chip, Toggle } from '../../components/ui'
import { SelectField } from '../../components/SelectField'
import { EASE } from '../../components/tokens'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet'
import { formatDateTime } from '../../lib/format'
import type { Channel } from '../../lib/publishing'
import { useCreatePost, useDeleteChannel, useUpdateChannel } from '../../lib/publishingQueries'
import { useProfiles } from '../../lib/queries'
import { ChannelSettingsForm } from './ChannelSettingsForm'

const LINK_LABEL = {
  inline: 'ссылка в тексте',
  button: 'кнопка',
  preview: 'карточка',
  none: 'без ссылки',
}

export function ChannelCard({
  channel,
  isSelected,
  onSelect,
  index,
}: {
  channel: Channel
  isSelected: boolean
  onSelect: () => void
  index: number
}) {
  const { data: profiles } = useProfiles()
  const update = useUpdateChannel()
  const remove = useDeleteChannel()
  const create = useCreatePost()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { settings } = channel
  const schedule =
    settings.schedule.mode === 'interval'
      ? `каждые ${settings.schedule.every_minutes} мин, ${settings.schedule.window_start}-${settings.schedule.window_end}`
      : settings.schedule.times.join(', ')

  const write = (publish: boolean) =>
    create.mutate(
      { channelId: channel.id, publish },
      {
        onSuccess: () =>
          toast.success(publish ? 'Публикуем пост' : 'Создаём черновик', {
            description: 'Пост появится в очереди через несколько секунд.',
          }),
      },
    )

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE, delay: index * 0.05 }}
    >
      <Card
        className={clsx(
          'p-5 transition-[box-shadow,outline-color]',
          isSelected ? 'outline-2 outline-primary' : 'hover:shadow-elevation-2',
        )}
      >
        <div className="flex items-start gap-3">
          {/* The name filters the queue by this channel; the switch beside it is its own control. */}
          <button
            type="button"
            onClick={onSelect}
            aria-pressed={isSelected}
            title={isSelected ? 'Показать посты всех каналов' : 'Показать посты этого канала'}
            className="flex min-w-0 flex-1 items-start gap-3 rounded-2xl text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
          >
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-primary-container text-lg font-semibold text-on-primary-container">
              {channel.title.slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-base font-medium">{channel.title}</span>
              <span className="block truncate text-sm text-muted-foreground">
                {channel.username ? `@${channel.username}` : `id ${channel.chat_id}`} · бот @
                {channel.bot_username}
              </span>
            </span>
          </button>
          <Toggle
            checked={channel.enabled}
            onChange={(enabled) => update.mutate({ id: channel.id, enabled })}
            label={channel.enabled ? 'Выключить автопостинг' : 'Включить автопостинг'}
          />
        </div>

        {channel.status !== 'ok' && channel.last_error && (
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-error-container px-3 py-2 text-xs text-on-error-container">
            <TriangleAlert size={14} className="mt-0.5 shrink-0" /> {channel.last_error}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-1.5">
          <Chip tone="accent">
            {settings.format.kind === 'rich' ? 'rich-посты' : 'обычные посты'}
          </Chip>
          <Chip>{LINK_LABEL[settings.links.mode]}</Chip>
          {settings.approval === 'manual' && <Chip tone="spark">с модерацией</Chip>}
          {settings.digest.enabled && <Chip>обзор недели</Chip>}
          {(channel.counts.sent ?? 0) > 0 && (
            <Chip tone="ok">опубликовано: {channel.counts.sent}</Chip>
          )}
          {(channel.counts.draft ?? 0) > 0 && (
            <Chip tone="spark">черновиков: {channel.counts.draft}</Chip>
          )}
        </div>

        <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <CalendarClock size={14} />
          {channel.enabled && channel.next_slot
            ? `следующий пост ${formatDateTime(channel.next_slot)} · ${schedule}`
            : channel.profile_id
              ? 'автопостинг выключен'
              : 'Выберите аудиторию, чтобы включить автопостинг'}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <SelectField
            value={channel.profile_id ?? ''}
            onChange={(value) => update.mutate({ id: channel.id, profile_id: value || null })}
            className="h-9 w-auto max-w-[220px] rounded-full text-[13px]"
            label="Аудитория канала"
            options={[
              { value: '', label: 'Без аудитории' },
              ...(profiles ?? []).map((profile) => ({
                value: profile.id,
                label: profile.spec.name,
              })),
            ]}
          />
          <Button
            size="sm"
            variant="tonal"
            icon={<FilePen size={15} />}
            isBusy={create.isPending && !create.variables?.publish}
            onClick={() => write(false)}
          >
            Создать черновик
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Send size={15} />}
            isBusy={create.isPending && Boolean(create.variables?.publish)}
            onClick={() => write(true)}
          >
            Опубликовать сейчас
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<Settings2 size={15} />}
            onClick={() => setSettingsOpen(true)}
          >
            Настроить
          </Button>
          <Button
            size="sm"
            variant="danger"
            aria-label="Отключить канал"
            icon={<Trash2 size={15} />}
            onClick={() => {
              if (window.confirm(`Отключить «${channel.title}»? Его посты удалятся из очереди.`))
                remove.mutate(channel.id)
            }}
          />
        </div>
      </Card>

      <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
        <SheetContent className="w-full overflow-y-auto rounded-l-[28px] p-6 data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
          <SheetHeader className="p-0">
            <SheetTitle>{channel.title}</SheetTitle>
            <SheetDescription>Стиль текстов, расписание и тематика публикаций.</SheetDescription>
          </SheetHeader>
          <ChannelSettingsForm
            key={channel.id}
            initial={settings}
            isBusy={update.isPending}
            onSave={(next) =>
              update.mutate(
                { id: channel.id, settings: next },
                {
                  onSuccess: () => {
                    toast.success('Настройки сохранены')
                    setSettingsOpen(false)
                  },
                },
              )
            }
          />
        </SheetContent>
      </Sheet>
    </motion.div>
  )
}
