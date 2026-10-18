// Pictures of the sections that are set up: interests, channels, sources and the account.
import clsx from 'clsx'
import {
  Bot,
  Check,
  ExternalLink,
  FileUp,
  Hub,
  Language,
  LibraryAdd,
  Rss,
  Schedule,
  Search,
  Send,
} from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import type { Me } from '../../lib/api'
import { AVATAR_PRESETS, presetImage } from '../../lib/avatar'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { Bar, Mini, Pill, PreviewFrame, Tile } from './PreviewParts'

const PROFILES = [
  { icon: 'shield', color: 'red', spec: { name: 'Специалист по ИБ' } },
  { icon: 'servers', color: 'blue', spec: { name: 'ИТ-инфраструктура' } },
  { icon: 'energy', color: 'amber', spec: { name: 'Энергетика' } },
]

/** A switch drawn on, as the app's own toggle. */
function SwitchOn() {
  return (
    <span className="flex h-5 w-8 shrink-0 items-center justify-end rounded-full bg-accent">
      <span className="mx-0.5 size-4 rounded-full bg-white shadow-sm" />
    </span>
  )
}

function Tick({ isOn }: { isOn: boolean }) {
  return (
    <span
      className={clsx(
        'grid size-3.5 shrink-0 place-items-center rounded',
        isOn ? 'bg-accent text-white dark:text-[#0b0f17]' : 'ring-1 ring-border',
      )}
    >
      {isOn && <Check size={9} />}
    </span>
  )
}

export function ProfilesPreview() {
  return (
    <PreviewFrame>
      <Mini index={0} className="flex flex-wrap gap-1.5 p-2">
        {PROFILES.map((look, index) => (
          <span
            key={look.spec.name}
            className={clsx(
              'flex items-center gap-1.5 rounded-full py-0.5 pr-2.5 pl-0.5 text-[11px]',
              index === 0 && 'bg-accent-soft font-medium ring-1 ring-accent/40',
            )}
          >
            <ProfileAvatar profile={look} size={20} />
            {look.spec.name}
          </span>
        ))}
      </Mini>
      <Mini index={1}>
        <div className="flex items-center gap-2">
          <p className="min-w-0 flex-1 text-[12px] font-semibold">Подстройка по отметкам</p>
          <SwitchOn />
        </div>
        <div className="mt-2 rounded-xl bg-surface-secondary p-2.5">
          <p className="flex items-center gap-1 text-[10px] text-muted">
            <LibraryAdd size={11} />
            Новая тема · по вашим отметкам
          </p>
          <p className="mt-1 text-[12px] font-semibold">Резервные центры обработки данных</p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <Pill>ЦОД</Pill>
            <Pill>резервирование</Pill>
          </div>
          <div className="mt-2 flex justify-end gap-1.5 text-[11px]">
            <span className="rounded-full px-2 py-0.5">Отклонить</span>
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-accent-soft-foreground">
              Добавить в профиль
            </span>
          </div>
        </div>
      </Mini>
      <Mini index={2}>
        <p className="text-[12px] font-semibold">Блоки выпуска</p>
        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
          {[
            ['Матрица риска', true],
            ['План на смену', true],
            ['Короткое видео', true],
            ['Не вошло в выпуск', false],
          ].map(([label, isOn]) => (
            <span key={String(label)} className="flex min-w-0 items-center gap-1.5">
              <Tick isOn={Boolean(isOn)} />
              <span className={clsx('truncate', !isOn && 'text-muted line-through')}>{label}</span>
            </span>
          ))}
        </div>
      </Mini>
    </PreviewFrame>
  )
}

export function ChannelsPreview() {
  return (
    <PreviewFrame>
      <Mini index={0} className="flex items-center gap-2.5 py-2.5">
        <Tile icon={Bot} size={30} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12px] font-semibold">Новости ИБ для смены</span>
          <span className="block text-[11px] text-muted">канал · бот подключён</span>
        </span>
        <Pill tone="ok">включён</Pill>
      </Mini>
      <div className="chat-wallpaper space-y-2 rounded-2xl p-2.5">
        {[0, 1].map((index) => (
          <Mini
            key={index}
            index={index + 1}
            className="max-w-[88%] rounded-[18px] rounded-bl-md p-2.5"
          >
            <p className="text-[12px] font-semibold">
              {index === 0
                ? 'Критическая уязвимость в SCADA-сервере'
                : 'Регулятор обновил требования к КИИ'}
            </p>
            <Bar className="mt-1.5 w-full" />
            <Bar className="mt-1 w-3/4" />
            <p className="mt-1.5 flex items-center justify-between text-[10px] text-muted">
              <span className="text-accent">Источник</span>
              {index === 0 ? '09:00' : '13:00'}
            </p>
          </Mini>
        ))}
      </div>
      <Mini index={3} className="flex flex-wrap items-center gap-1.5 p-2.5">
        <Schedule size={14} className="text-accent" />
        <Pill>Пн-Пт</Pill>
        <Pill>09:00</Pill>
        <Pill>13:00</Pill>
        <Pill>18:00</Pill>
        <Pill tone="accent">после проверки</Pill>
      </Mini>
    </PreviewFrame>
  )
}

const SOURCES: { icon: IconComponent; name: string; kind: string; isQuiet?: boolean }[] = [
  { icon: Rss, name: 'CISA ICS Advisories', kind: 'RSS' },
  { icon: Send, name: 'Россети', kind: 'Telegram' },
  { icon: Language, name: 'SecurityLab.ru', kind: 'сайт' },
  { icon: Rss, name: 'Хабр: Информационная безопасность', kind: 'RSS', isQuiet: true },
]

export function SourcesPreview() {
  return (
    <PreviewFrame>
      <Mini index={0} className="flex items-center gap-2 py-2">
        <Search size={14} className="shrink-0 text-muted" />
        <span className="min-w-0 flex-1 truncate text-[12px] text-muted">
          Поиск по публикациям: уязвимость SCADA
        </span>
        <Pill tone="accent">по смыслу</Pill>
      </Mini>
      <Mini index={1} className="p-0">
        <ul className="divide-y divide-separator">
          {SOURCES.map((source) => (
            <li key={source.name} className="flex items-center gap-2.5 px-3 py-2">
              <Tile icon={source.icon} size={24} />
              <span className="min-w-0 flex-1 truncate text-[12px]">{source.name}</span>
              <span className="hidden text-[10px] text-muted min-[400px]:inline">
                {source.kind}
              </span>
              <span
                className={clsx(
                  'size-1.5 shrink-0 rounded-full',
                  source.isQuiet ? 'bg-warning' : 'bg-success',
                )}
              />
            </li>
          ))}
        </ul>
      </Mini>
      <Mini index={2} className="flex items-center gap-2 py-2.5">
        <span className="min-w-0 flex-1 space-y-1">
          <span className="block truncate text-[12px] font-semibold">
            Siemens выпустила обновления для SIMATIC
          </span>
          <span className="block text-[10px] text-muted">CISA ICS Advisories · сегодня</span>
        </span>
        <span className="flex shrink-0 items-center gap-1 rounded-full bg-accent-soft px-2 py-1 text-[11px] text-accent-soft-foreground">
          <ExternalLink size={12} />
          Оригинал
        </span>
      </Mini>
    </PreviewFrame>
  )
}

export function AccountPreview({ me }: { me?: Me | null }) {
  const preset = me?.avatar_preset
  const chosen = AVATAR_PRESETS.some((item) => item.key === preset) ? preset : 'sky'
  return (
    <PreviewFrame>
      <Mini index={0}>
        <p className="text-[12px] font-semibold">Картинка профиля</p>
        <div className="mt-2 grid grid-cols-9 gap-1">
          {AVATAR_PRESETS.map((item) => {
            const image = presetImage(item.key)
            return (
              <img
                key={item.key}
                src={image.src}
                srcSet={image.srcSet}
                alt=""
                width={30}
                height={30}
                decoding="async"
                draggable={false}
                className={clsx(
                  'aspect-square w-full rounded-full object-contain',
                  item.key === chosen && 'ring-2 ring-accent ring-offset-1 ring-offset-surface',
                )}
              />
            )
          })}
        </div>
      </Mini>
      <Mini index={1} className="flex items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-dashed border-border text-muted">
          <FileUp size={18} />
        </span>
        <span className="min-w-0">
          <span className="block text-[12px] font-semibold">Резюме</span>
          <span className="block text-[11px] text-muted">PDF, DOCX, TXT, MD, HTML</span>
        </span>
      </Mini>
      <Mini index={2}>
        <p className="flex items-center gap-2 text-[12px] font-semibold">
          <Tile icon={Hub} size={24} />
          Доступ для ИИ-ассистентов
        </p>
        <p className="mt-2 truncate rounded-lg bg-surface-secondary px-2.5 py-1.5 font-mono text-[11px]">
          https://…/api/mcp/
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          <Pill>Claude Code</Pill>
          <Pill>Claude Desktop</Pill>
          <Pill>Cursor</Pill>
        </div>
      </Mini>
    </PreviewFrame>
  )
}
