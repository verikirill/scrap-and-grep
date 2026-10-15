import { KeyRound, Send } from '../components/icons'
import { useState } from 'react'
import { Loading, SkeletonCard } from '../components/loading'
import { Card, EmptyState, PageHeader } from '../components/ui'
import { AddChannelDialog } from '../features/channels/AddChannelDialog'
import { BotsPanel } from '../features/channels/BotsPanel'
import { ChannelCard } from '../features/channels/ChannelCard'
import { PostsPanel } from '../features/channels/PostsPanel'
import { Segmented } from '../components/Segmented'
import { useChannels, usePublishingDefaults } from '../lib/publishingQueries'
import { useMe } from '../lib/queries'

// How a channel gets connected, shown where the list of channels will be.
const CHANNEL_STEPS = [
  'Создайте бота у @BotFather и вставьте его токен в блок «Боты»',
  'Добавьте бота администратором в свой канал',
  'Нажмите «Добавить канал» и выберите тон и расписание',
]

export function ChannelsPage() {
  const { data: defaults } = usePublishingDefaults()
  const me = useMe()
  // How to turn publishing on is the operator's business; a reader learns only that it is off.
  const isAdmin = Boolean(me.data?.is_admin && !me.data.is_demo)
  const { data: channels, isPending } = useChannels()
  const [selected, setSelected] = useState<string>('all')
  const isMock = defaults?.mock ?? false
  // A channel removed while chosen leaves the filter on all of them.
  const active = channels?.some((channel) => channel.id === selected) ? selected : 'all'

  return (
    <>
      <PageHeader
        title="Каналы"
        subtitle="Боты сами публикуют новости в ваши Telegram-каналы по расписанию. Отбор, тон постов и оформление ссылок настраиваются для каждого канала."
        actions={<AddChannelDialog />}
      />

      {defaults && !defaults.enabled && (
        <Card variant="filled" className="mb-6 flex items-start gap-3 p-5">
          <KeyRound size={20} className="mt-0.5 shrink-0 text-warning" />
          {isAdmin ? (
            <p className="text-sm">
              Публикация выключена, потому что на сервере не задан ключ шифрования токенов ботов.
            </p>
          ) : (
            <p className="text-sm">
              Публикация в Telegram на этом стенде пока выключена. Включить её может администратор.
            </p>
          )}
        </Card>
      )}
      {isMock && (
        <p className="mb-6 rounded-2xl bg-default px-4 py-3 text-sm text-default-foreground">
          Стенд подключён к тестовому эмулятору Telegram, подойдёт любой токен вида 123456789:AA… и
          любой @канал. Публикации видны на порту 8089.
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="space-y-4">
          <BotsPanel />
          {isPending && (
            <Loading label="Загружаем каналы">
              <SkeletonCard className="h-56" />
            </Loading>
          )}
          {channels?.length === 0 && (
            <Card variant="outlined">
              <EmptyState icon={<Send size={22} />} title="Каналов пока нет">
                <ol className="mt-3 grid gap-2 text-left">
                  {CHANNEL_STEPS.map((text, index) => (
                    <li key={text} className="flex gap-2.5 rounded-xl bg-surface-secondary p-3">
                      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-soft-foreground">
                        {index + 1}
                      </span>
                      <span className="text-[13px] text-foreground">{text}</span>
                    </li>
                  ))}
                </ol>
              </EmptyState>
            </Card>
          )}
          {channels?.map((channel, index) => (
            <ChannelCard
              key={channel.id}
              channel={channel}
              index={index}
              isSelected={active === channel.id}
              onSelect={() => setSelected(active === channel.id ? 'all' : channel.id)}
            />
          ))}
        </div>

        <section aria-label="Посты" className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-normal">Очередь и история</h2>
            {channels && channels.length > 1 && (
              <div className="max-w-full min-w-0">
                <Segmented
                  label="Канал"
                  value={active}
                  onChange={setSelected}
                  isScrollable
                  options={[
                    { value: 'all', label: 'Все' },
                    ...channels.map((channel) => ({ value: channel.id, label: channel.title })),
                  ]}
                />
              </div>
            )}
          </div>
          <PostsPanel channelId={active === 'all' ? undefined : active} channels={channels ?? []} />
        </section>
      </div>
    </>
  )
}
