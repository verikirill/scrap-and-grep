// Pictures of the sections that are read: the digest, the feed and the comparison.
import clsx from 'clsx'
import {
  ArrowRight,
  ArrowUp,
  Bookmark,
  Check,
  Clapperboard,
  EyeOff,
  Minus,
  Plus,
  Sparkles,
  Target,
  ThumbsDown,
  ThumbsUp,
  ViewCards,
  ViewChat,
} from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import { ProfileAvatar } from '../profiles/ProfileLook'
import { Bar, Mini, Pill, PreviewFrame } from './PreviewParts'

// The risk matrix in miniature: severity up, closeness to the reader's systems across.
const MATRIX = [
  [0, 1, 2],
  [1, 0, 1],
  [2, 1, 0],
]

export function DigestPreview() {
  return (
    <PreviewFrame>
      <Mini index={0} className="bg-accent-soft shadow-none">
        <p className="text-[11px] text-accent-soft-foreground">
          Специалист по ИБ АСУ ТП · 8 окт. - 15 окт.
        </p>
        <p className="mt-1 font-serif text-[17px] leading-snug font-semibold text-accent-soft-foreground">
          Главное за неделю: уязвимости и атаки
        </p>
      </Mini>
      <div className="grid grid-cols-2 gap-2.5">
        <Mini index={1}>
          <p className="flex items-center gap-1.5 text-[11px] font-semibold">
            <Target size={13} className="text-accent" />
            Матрица риска
          </p>
          <div className="mt-2 grid grid-cols-3 gap-1">
            {MATRIX.flatMap((row, y) =>
              row.map((level, x) => (
                <span
                  key={`${y}-${x}`}
                  className={clsx(
                    'grid h-7 place-items-center rounded-md',
                    y === 0 && x === 2 ? 'bg-danger-soft' : 'bg-default',
                  )}
                >
                  {level > 0 && (
                    <span
                      className={clsx(
                        'size-1.5 rounded-full',
                        y === 0 && x === 2 ? 'bg-danger' : 'bg-warning',
                      )}
                    />
                  )}
                </span>
              )),
            )}
          </div>
        </Mini>
        <Mini index={2}>
          <p className="text-[11px] font-semibold">План на смену</p>
          <ul className="mt-2 space-y-1.5">
            {[true, true, false].map((isDone, index) => (
              <li key={index} className="flex items-center gap-1.5">
                <span
                  className={clsx(
                    'grid size-3.5 shrink-0 place-items-center rounded-full',
                    isDone ? 'bg-accent text-white dark:text-[#0b0f17]' : 'ring-1 ring-border',
                  )}
                >
                  {isDone && <Check size={9} />}
                </span>
                <Bar className={clsx(index === 2 ? 'w-3/5' : 'w-full', isDone && 'opacity-60')} />
              </li>
            ))}
          </ul>
          <Pill className="mt-2.5">
            <Clapperboard size={12} />
            Короткое видео
          </Pill>
        </Mini>
      </div>
      <Mini index={3} className="flex items-center gap-2 rounded-full py-2 pr-2 pl-3">
        <Sparkles size={15} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 truncate text-[12px] text-muted">
          Спросить выпуск: что обновить первым?
        </span>
        <span className="grid size-6 shrink-0 place-items-center rounded-full ring-1 ring-border">
          <ArrowUp size={12} />
        </span>
      </Mini>
    </PreviewFrame>
  )
}

const REACTIONS: { icon: IconComponent; isOn?: boolean }[] = [
  { icon: ThumbsUp, isOn: true },
  { icon: ThumbsDown },
  { icon: Bookmark },
  { icon: EyeOff },
]

export function FeedPreview() {
  return (
    <PreviewFrame>
      <div className="flex justify-end">
        <span className="inline-flex rounded-full bg-surface p-0.5 text-[11px] ring-1 ring-border">
          <span className="flex items-center gap-1 rounded-full px-2.5 py-1 text-muted">
            <ViewCards size={12} />
            Карточки
          </span>
          <span className="flex items-center gap-1 rounded-full bg-default px-2.5 py-1 font-medium">
            <ViewChat size={12} />
            Посты
          </span>
        </span>
      </div>
      <Mini index={0}>
        <p className="text-[11px] text-muted">Хабр · вчера · 4 мин чтения</p>
        <p className="mt-1 font-serif text-[15px] leading-snug font-semibold">
          Как обновить контроллеры без остановки линии
        </p>
        <Bar className="mt-2 w-full" />
        <Bar className="mt-1.5 w-4/5" />
        <div className="mt-2.5 flex items-center justify-between gap-2">
          <Pill tone="accent" className="min-w-0 truncate">
            Интерес «Безопасность АСУ ТП»
          </Pill>
          <span className="flex shrink-0 items-center gap-2 text-muted">
            {REACTIONS.map(({ icon: Icon, isOn }, index) => (
              <Icon
                key={index}
                size={14}
                filled={isOn}
                className={isOn ? 'text-accent' : undefined}
              />
            ))}
          </span>
        </div>
      </Mini>
      <div className="chat-wallpaper rounded-2xl p-2.5">
        <Mini index={1} className="ml-auto max-w-[86%] rounded-[18px] rounded-br-md p-2.5">
          <p className="text-[12px] font-semibold">Ростелеком: новый ЦОД в Сибири</p>
          <Bar className="mt-1.5 w-full" />
          <Bar className="mt-1 w-2/3" />
          <p className="mt-1.5 text-right text-[10px] text-muted">12:40</p>
        </Mini>
      </div>
      <Mini index={2} className="flex items-center gap-2 rounded-full py-2">
        <ThumbsUp size={14} filled className="text-accent" />
        <span className="text-[12px]">Учтено: похожего станет больше</span>
      </Mini>
    </PreviewFrame>
  )
}

function CompareColumn({
  index,
  icon: Icon,
  title,
  count,
  tone,
}: {
  index: number
  icon: IconComponent
  title: string
  count: number
  tone: 'ok' | 'danger' | 'neutral'
}) {
  return (
    <Mini index={index} className="min-w-0 p-2.5">
      <p className="flex items-center gap-1.5 text-[11px] font-semibold">
        <span
          className={clsx(
            'grid size-4 shrink-0 place-items-center rounded',
            tone === 'ok' && 'bg-success-soft text-success-soft-foreground',
            tone === 'danger' && 'bg-danger-soft text-danger-soft-foreground',
            tone === 'neutral' && 'bg-default text-muted',
          )}
        >
          <Icon size={10} />
        </span>
        <span className="min-w-0 flex-1 truncate">{title}</span>
        <span className="tabular text-muted">{count}</span>
      </p>
      {[0.94, 0.81].map((score) => (
        <div key={score} className="mt-2 flex items-start gap-1.5">
          <span className="min-w-0 flex-1 space-y-1">
            <Bar className="w-full" />
            <Bar className="w-2/3 opacity-60" />
          </span>
          <span className="tabular text-[10px] text-muted">{score.toFixed(2)}</span>
        </div>
      ))}
    </Mini>
  )
}

export function ComparePreview() {
  const looks = [
    { icon: 'shield', color: 'red', spec: { name: 'Было' } },
    { icon: 'shield', color: 'violet', spec: { name: 'Стало' } },
  ]
  return (
    <PreviewFrame>
      <div className="flex items-center gap-2">
        {looks.map((look, index) => (
          <Mini
            key={look.spec.name}
            index={index}
            className={clsx(
              'flex min-w-0 flex-1 items-center gap-2 py-2',
              index === 1 && 'order-3',
            )}
          >
            <ProfileAvatar profile={look} size={22} />
            <span className="min-w-0 truncate text-[12px]">
              {look.spec.name}: {index === 0 ? '8 окт.' : '15 окт.'}
            </span>
          </Mini>
        ))}
        <ArrowRight size={14} className="order-2 shrink-0 text-muted" />
      </div>
      <Mini index={2} className="p-2.5">
        <p className="text-[10px] font-semibold tracking-wide text-muted uppercase">
          Что изменили в профиле
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <Pill tone="ok">ЦОД и облака: добавлен</Pill>
          <Pill tone="danger">Регуляторы: убран</Pill>
        </div>
      </Mini>
      <div className="grid grid-cols-3 gap-2">
        <CompareColumn index={3} icon={Plus} title="Появилось" count={6} tone="ok" />
        <CompareColumn index={4} icon={Minus} title="Ушло" count={4} tone="danger" />
        <CompareColumn index={5} icon={ArrowRight} title="Осталось" count={9} tone="neutral" />
      </div>
    </PreviewFrame>
  )
}
