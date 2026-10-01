import { cn } from '../../lib/utils'
import clsx from 'clsx'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChipsInput } from '../../components/ChipsInput'
import { Button, Field, Toggle } from '../../components/ui'
import { INPUT_CLASS } from '../../components/tokens'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'
import { WEEKDAYS } from '../../lib/publishing'
import type { ChannelSettings } from '../../lib/publishing'
import { Segmented } from '../../components/Segmented'

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/
const SECTIONS = [
  ['voice', 'Голос'],
  ['links', 'Ссылки'],
  ['format', 'Формат'],
  ['schedule', 'Расписание'],
  ['selection', 'Отбор'],
] as const

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-4 py-1.5 text-sm">
      <span>{label}</span>
      {children}
    </label>
  )
}

function Range({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
}: {
  value: number
  min: number
  max: number
  step?: number
  onChange: (value: number) => void
  label: string
}) {
  const fill = `${((value - min) / (max - min)) * 100}%`
  return (
    <input
      type="range"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      style={{ '--fill': fill } as React.CSSProperties}
      onChange={(event) => onChange(Number(event.target.value))}
      className="w-full"
    />
  )
}

/**
 * Everything a channel can be told: its voice, links, format, when it posts,
 * which stories qualify, the weekly round-up and whether a human approves.
 */
export function ChannelSettingsForm({
  initial,
  isBusy,
  onSave,
}: {
  initial: ChannelSettings
  isBusy?: boolean
  onSave: (settings: ChannelSettings) => void
}) {
  const [settings, setSettings] = useState(initial)
  const set = <K extends keyof ChannelSettings>(key: K, patch: Partial<ChannelSettings[K]>) =>
    setSettings((current) => ({
      ...current,
      [key]: { ...(current[key] as object), ...patch },
    }))
  const { style, links, format, schedule, selection, digest } = settings
  const timesValid =
    schedule.mode !== 'times' ||
    (schedule.times.length > 0 && schedule.times.every((time) => TIME_RE.test(time)))

  return (
    <div className="flex h-full flex-col">
      <Tabs defaultValue="voice" className="min-h-0 flex-1">
        {/* Material primary tabs: an underline in the primary colour, scrolled on a phone. */}
        <TabsList
          variant="line"
          className="h-12! w-full justify-start overflow-x-auto border-b border-outline-variant p-0"
        >
          {SECTIONS.map(([value, label]) => (
            <TabsTrigger
              key={value}
              value={value}
              className="h-full flex-1 px-3 text-[14px] text-on-surface-variant after:bottom-0! after:rounded-t-full after:bg-primary data-active:text-primary"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="voice" className="space-y-4 pt-4">
          <Field label="Тон" isGroup>
            <Segmented
              label="Тон"
              value={style.tone}
              onChange={(tone) => set('style', { tone })}
              options={[
                { value: 'punchy', label: 'Живой' },
                { value: 'neutral', label: 'Сдержанный' },
                { value: 'expert', label: 'Экспертный' },
                { value: 'custom', label: 'Свой' },
              ]}
            />
          </Field>
          <Field label="Пожелания к тексту" hint="например: на «вы», без жаргона">
            <textarea
              value={style.instructions}
              maxLength={1000}
              rows={3}
              onChange={(event) => set('style', { instructions: event.target.value })}
              className={cn(INPUT_CLASS, 'h-auto py-2.5')}
            />
          </Field>
          <Field label="Аудитория" hint="пусто - роль из профиля">
            <input
              value={style.audience}
              maxLength={600}
              onChange={(event) => set('style', { audience: event.target.value })}
              className={INPUT_CLASS}
              placeholder="например: администраторы АСУ ТП"
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Эмодзи в начале">
              <input
                value={style.emoji}
                maxLength={8}
                onChange={(event) => set('style', { emoji: event.target.value })}
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Подпись под постом">
              <input
                value={style.signature}
                maxLength={64}
                onChange={(event) => set('style', { signature: event.target.value })}
                className={INPUT_CLASS}
              />
            </Field>
          </div>
          <Field label="Длина" isGroup>
            <Segmented
              label="Длина"
              value={style.length}
              onChange={(length) => set('style', { length })}
              options={[
                { value: 'short', label: 'Коротко' },
                { value: 'medium', label: 'Средне' },
                { value: 'long', label: 'Подробно' },
              ]}
            />
          </Field>
          <div className="divide-y divide-outline-variant">
            <Row label="Списки, когда в новости перечисление">
              <Toggle
                checked={style.bullets}
                onChange={(bullets) => set('style', { bullets })}
                label="Списки"
              />
            </Row>
            <Row label="Живая реплика в конце">
              <Toggle
                checked={style.ending}
                onChange={(ending) => set('style', { ending })}
                label="Реплика"
              />
            </Row>
            <Row label="Хэштеги">
              <Toggle
                checked={style.hashtags}
                onChange={(hashtags) => set('style', { hashtags })}
                label="Хэштеги"
              />
            </Row>
          </div>
        </TabsContent>

        <TabsContent value="links" className="space-y-4 pt-4">
          <Field label="Где ссылка на источник" isGroup>
            <Segmented
              label="Ссылка"
              value={links.mode}
              onChange={(mode) => set('links', { mode })}
              options={[
                { value: 'inline', label: 'Словом' },
                { value: 'button', label: 'Кнопкой' },
                { value: 'preview', label: 'Карточкой' },
                { value: 'none', label: 'Без ссылки' },
              ]}
            />
          </Field>
          <p className="px-1 text-xs text-muted-foreground">
            «Словом» - в конце поста «Подробности - здесь», «Карточкой» - превью статьи с её
            картинкой, «Без ссылки» - только текст. Разные каналы могут вести одну и ту же новость
            по-разному.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Слово-ссылка">
              <input
                value={links.inline_text}
                maxLength={40}
                onChange={(event) => set('links', { inline_text: event.target.value })}
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Текст кнопки">
              <input
                value={links.button_text}
                maxLength={40}
                onChange={(event) => set('links', { button_text: event.target.value })}
                className={INPUT_CLASS}
              />
            </Field>
          </div>
          <Field label="Метки к адресу" hint="utm_source=tg&utm_medium=channel">
            <input
              value={links.utm}
              maxLength={200}
              onChange={(event) => set('links', { utm: event.target.value })}
              className={INPUT_CLASS}
            />
          </Field>
        </TabsContent>

        <TabsContent value="format" className="space-y-4 pt-4">
          <Field label="Вид поста" isGroup>
            <Segmented
              label="Вид поста"
              value={format.kind}
              onChange={(kind) => set('format', { kind })}
              options={[
                { value: 'classic', label: 'Обычный' },
                { value: 'rich', label: 'Rich (новый редактор)' },
              ]}
            />
          </Field>
          <p className="px-1 text-xs text-muted-foreground">
            Rich-пост - формат нового редактора Telegram (июль 2026): заголовки, списки, цитаты,
            слайдшоу картинок, до 32 768 знаков. Обычный пост - картинка с подписью до 1024 знаков
            или текст до 4096.
          </p>
          <div className="divide-y divide-outline-variant">
            <Row label="Картинка статьи, если есть">
              <Toggle
                checked={format.media === 'auto'}
                onChange={(on) => set('format', { media: on ? 'auto' : 'none' })}
                label="Картинка"
              />
            </Row>
            <Row label="Подпись над картинкой">
              <Toggle
                checked={format.caption_above_media}
                onChange={(caption_above_media) => set('format', { caption_above_media })}
                label="Подпись над картинкой"
              />
            </Row>
            <Row label="Без звука у подписчиков">
              <Toggle
                checked={format.silent}
                onChange={(silent) => set('format', { silent })}
                label="Без звука"
              />
            </Row>
            <Row label="Запретить пересылку и сохранение">
              <Toggle
                checked={format.protect_content}
                onChange={(protect_content) => set('format', { protect_content })}
                label="Защита"
              />
            </Row>
          </div>
          <div className="rounded-2xl bg-surface-container p-4">
            <Row label="Еженедельный обзор rich-постом">
              <Toggle
                checked={digest.enabled}
                onChange={(enabled) => set('digest', { enabled })}
                label="Обзор"
              />
            </Row>
            {digest.enabled && (
              <div className="mt-3 grid grid-cols-3 gap-3">
                <Field label="День">
                  <select
                    value={digest.weekday}
                    onChange={(event) => set('digest', { weekday: Number(event.target.value) })}
                    className={INPUT_CLASS}
                  >
                    {WEEKDAYS.map((day, index) => (
                      <option key={day} value={index}>
                        {day}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Время">
                  <input
                    type="time"
                    value={digest.time}
                    onChange={(event) => set('digest', { time: event.target.value })}
                    className={INPUT_CLASS}
                  />
                </Field>
                <Field label="Новостей">
                  <input
                    type="number"
                    min={3}
                    max={10}
                    value={digest.items}
                    onChange={(event) => set('digest', { items: Number(event.target.value) })}
                    className={INPUT_CLASS}
                  />
                </Field>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-4 pt-4">
          <Field label="Как часто" isGroup>
            <Segmented
              label="Режим"
              value={schedule.mode}
              onChange={(mode) => set('schedule', { mode })}
              options={[
                { value: 'interval', label: 'Каждые N минут' },
                { value: 'times', label: 'В заданное время' },
              ]}
            />
          </Field>
          {schedule.mode === 'interval' ? (
            <>
              <Field label="Интервал" hint={`${schedule.every_minutes} мин`}>
                <Range
                  label="Интервал"
                  min={15}
                  max={720}
                  step={15}
                  value={schedule.every_minutes}
                  onChange={(every_minutes) => set('schedule', { every_minutes })}
                />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="С">
                  <input
                    type="time"
                    value={schedule.window_start}
                    onChange={(event) => set('schedule', { window_start: event.target.value })}
                    className={INPUT_CLASS}
                  />
                </Field>
                <Field label="До">
                  <input
                    type="time"
                    value={schedule.window_end}
                    onChange={(event) => set('schedule', { window_end: event.target.value })}
                    className={INPUT_CLASS}
                  />
                </Field>
              </div>
            </>
          ) : (
            <Field label="Время постов" hint="09:00, 13:30" isGroup>
              <ChipsInput
                label="Время постов"
                values={schedule.times}
                onChange={(times) => set('schedule', { times })}
                placeholder="09:00, Enter"
                max={48}
              />
            </Field>
          )}
          <Field label="Дни" isGroup>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((day, index) => {
                const isOn = schedule.days.includes(index)
                return (
                  <button
                    key={day}
                    type="button"
                    aria-pressed={isOn}
                    onClick={() =>
                      set('schedule', {
                        days: isOn
                          ? schedule.days.filter((value) => value !== index)
                          : [...schedule.days, index].sort(),
                      })
                    }
                    className={clsx(
                      'state-layer relative h-9 w-11 overflow-hidden rounded-lg text-sm font-medium',
                      isOn
                        ? 'bg-secondary-container text-on-secondary-container'
                        : 'border border-outline-variant text-on-surface-variant',
                    )}
                  >
                    {day}
                  </button>
                )
              })}
            </div>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Постов в день, не больше" hint={String(schedule.max_per_day)}>
              <Range
                label="Постов в день"
                min={1}
                max={24}
                value={schedule.max_per_day}
                onChange={(max_per_day) => set('schedule', { max_per_day })}
              />
            </Field>
            <Field label="Разброс времени" hint={`±${schedule.jitter_minutes} мин`}>
              <Range
                label="Разброс"
                min={0}
                max={60}
                step={5}
                value={schedule.jitter_minutes}
                onChange={(jitter_minutes) => set('schedule', { jitter_minutes })}
              />
            </Field>
          </div>
          <Field label="Готовить пост заранее" hint={`за ${schedule.prepare_minutes} мин`}>
            <Range
              label="Заранее"
              min={5}
              max={240}
              step={5}
              value={schedule.prepare_minutes}
              onChange={(prepare_minutes) => set('schedule', { prepare_minutes })}
            />
          </Field>
          <div className="rounded-2xl bg-surface-container p-4">
            <Row label="Перед публикацией показывать мне">
              <Toggle
                checked={settings.approval === 'manual'}
                onChange={(manual) =>
                  setSettings((current) => ({
                    ...current,
                    approval: manual ? 'manual' : 'auto',
                  }))
                }
                label="Модерация"
              />
            </Row>
            <p className="text-xs text-muted-foreground">
              Посты будут ждать в черновиках, пока вы их не одобрите.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="selection" className="space-y-4 pt-4">
          <Field label="Свежесть новостей" hint={`за ${selection.freshness_hours} ч`}>
            <Range
              label="Свежесть"
              min={1}
              max={168}
              value={selection.freshness_hours}
              onChange={(freshness_hours) => set('selection', { freshness_hours })}
            />
          </Field>
          <Field label="Порог релевантности" hint={selection.min_score.toFixed(2)}>
            <Range
              label="Порог"
              min={0}
              max={1}
              step={0.05}
              value={selection.min_score}
              onChange={(min_score) => set('selection', { min_score })}
            />
          </Field>
          <Field label="Одна новость в нескольких каналах" isGroup>
            <Segmented
              label="Сеть каналов"
              value={selection.network}
              onChange={(network) => set('selection', { network })}
              options={[
                { value: 'share', label: 'Можно, другими словами' },
                { value: 'spread', label: 'Разносить по времени' },
              ]}
            />
          </Field>
          {selection.network === 'spread' && (
            <Field
              label="Не повторять новость другого канала"
              hint={`${selection.network_hours} ч`}
            >
              <Range
                label="Пауза"
                min={1}
                max={72}
                value={selection.network_hours}
                onChange={(network_hours) => set('selection', { network_hours })}
              />
            </Field>
          )}
        </TabsContent>
      </Tabs>

      <div className="sticky bottom-0 flex gap-2 bg-popover pt-4 pb-1">
        <Button
          variant="primary"
          isBusy={isBusy}
          disabled={!timesValid}
          onClick={() => onSave(settings)}
        >
          Сохранить настройки
        </Button>
        {!timesValid && (
          <span className="self-center text-xs text-destructive">Время в формате 09:30</span>
        )}
      </div>
    </div>
  )
}
