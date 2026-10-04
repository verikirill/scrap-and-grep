import { cn } from '../../lib/utils'
import { Mark, mergeAttributes } from '@tiptap/react'
import { EditorContent, useEditor, useEditorState } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import clsx from 'clsx'
import {
  Bold,
  Code,
  EyeOff,
  Heading2,
  Italic,
  Link2,
  List,
  ListOrdered,
  Plus,
  Quote,
  Strikethrough,
  Trash2,
  Underline,
} from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import { useState } from 'react'
import { Button, Field, Toggle } from '../../components/ui'
import { SelectField } from '../../components/SelectField'
import { INPUT_CLASS } from '../../components/tokens'
import type { Media, PostButton, PostContent, PostFormat } from '../../lib/publishing'
import { visibleLength } from '../../lib/postText'
import { Segmented } from '../../components/Segmented'
import { TelegramPreview } from './TelegramPreview'

const MEDIA_KINDS = [
  { value: 'photo', label: 'Фото' },
  { value: 'video', label: 'Видео' },
]

/** Telegram's spoiler: text hidden under a veil until tapped. */
const Spoiler = Mark.create({
  name: 'spoiler',
  parseHTML: () => [{ tag: 'tg-spoiler' }, { tag: 'span.tg-spoiler' }],
  renderHTML: ({ HTMLAttributes }) => ['tg-spoiler', mergeAttributes(HTMLAttributes), 0],
  addKeyboardShortcuts() {
    return { 'Mod-Shift-p': () => this.editor.commands.toggleMark(this.name) }
  },
})

const LIMITS = { rich: 32768, caption: 1024, text: 4096 }

const FORMATS = [
  { value: 'classic', label: 'Обычный пост' },
  { value: 'rich', label: 'Rich-пост' },
] as const satisfies readonly { value: PostFormat; label: string }[]

function limitFor(format: PostFormat, media: Media[]): number {
  if (format === 'rich') return LIMITS.rich
  return media.length === 1 ? LIMITS.caption : LIMITS.text
}

type ToolProps = {
  icon: IconComponent
  label: string
  active?: boolean
  onClick: () => void
}

function Tool({ icon: Icon, label, active, onClick }: ToolProps) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className={clsx(
        'state-layer relative grid size-9 place-items-center overflow-hidden rounded-full transition-colors',
        active ? 'bg-secondary-container text-on-secondary-container' : 'text-on-surface-variant',
      )}
    >
      <Icon size={17} />
    </button>
  )
}

function useRichEditor(html: string, onChange: (html: string) => void) {
  return useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        horizontalRule: false,
        link: {
          openOnClick: false,
          autolink: true,
          defaultProtocol: 'https',
          isAllowedUri: (url, ctx) => ctx.defaultValidate(url) && /^(https?:|tg:)/i.test(url),
        },
      }),
      Spoiler,
    ],
    content: html,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
    editorProps: {
      attributes: {
        class:
          'prose-post min-h-56 px-4 py-3 text-[15px] leading-relaxed outline-none [&_blockquote]:border-l-[3px] [&_blockquote]:border-primary [&_blockquote]:pl-3 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_code]:rounded [&_code]:bg-surface-container-high [&_code]:px-1 [&_a]:text-primary [&_a]:underline [&_tg-spoiler]:rounded [&_tg-spoiler]:bg-outline/40',
      },
    },
  })
}

export function PostEditor({
  initial,
  channel,
  isBusy,
  onSave,
  onCancel,
}: {
  initial: PostContent
  channel: string
  isBusy?: boolean
  onSave: (content: PostContent, approve: boolean) => void
  onCancel: () => void
}) {
  const [content, setContent] = useState<PostContent>(initial)
  const update = (patch: Partial<PostContent>) =>
    setContent((current) => ({ ...current, ...patch }))
  const editor = useRichEditor(initial.html, (html) => update({ html }))
  const marks = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current?.isActive('bold') ?? false,
      italic: current?.isActive('italic') ?? false,
      underline: current?.isActive('underline') ?? false,
      strike: current?.isActive('strike') ?? false,
      spoiler: current?.isActive('spoiler') ?? false,
      code: current?.isActive('code') ?? false,
      link: current?.isActive('link') ?? false,
      quote: current?.isActive('blockquote') ?? false,
      heading: current?.isActive('heading') ?? false,
      bullets: current?.isActive('bulletList') ?? false,
      numbers: current?.isActive('orderedList') ?? false,
    }),
  })
  const length = visibleLength(content.html, content.format)
  const limit = limitFor(content.format, content.media)

  const setLink = () => {
    if (!editor) return
    const previous = editor.getAttributes('link').href as string | undefined
    const url = window.prompt('Ссылка (https://…)', previous ?? 'https://')
    if (url === null) return
    if (url === '') editor.chain().focus().unsetLink().run()
    else editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
  }

  const chain = () => editor?.chain().focus()
  const tools: ToolProps[] = [
    {
      icon: Bold,
      label: 'Жирный',
      active: marks?.bold,
      onClick: () => chain()?.toggleBold().run(),
    },
    {
      icon: Italic,
      label: 'Курсив',
      active: marks?.italic,
      onClick: () => chain()?.toggleItalic().run(),
    },
    {
      icon: Underline,
      label: 'Подчёркнутый',
      active: marks?.underline,
      onClick: () => chain()?.toggleUnderline().run(),
    },
    {
      icon: Strikethrough,
      label: 'Зачёркнутый',
      active: marks?.strike,
      onClick: () => chain()?.toggleStrike().run(),
    },
    {
      icon: EyeOff,
      label: 'Скрытый текст',
      active: marks?.spoiler,
      onClick: () => chain()?.toggleMark('spoiler').run(),
    },
    {
      icon: Code,
      label: 'Моноширинный',
      active: marks?.code,
      onClick: () => chain()?.toggleCode().run(),
    },
    { icon: Link2, label: 'Ссылка', active: marks?.link, onClick: setLink },
    {
      icon: Quote,
      label: 'Цитата',
      active: marks?.quote,
      onClick: () => chain()?.toggleBlockquote().run(),
    },
    {
      icon: Heading2,
      label: 'Заголовок',
      active: marks?.heading,
      onClick: () => chain()?.toggleHeading({ level: 2 }).run(),
    },
    {
      icon: List,
      label: 'Список',
      active: marks?.bullets,
      onClick: () => chain()?.toggleBulletList().run(),
    },
    {
      icon: ListOrdered,
      label: 'Нумерованный список',
      active: marks?.numbers,
      onClick: () => chain()?.toggleOrderedList().run(),
    },
  ]

  const setMedia = (index: number, patch: Partial<Media>) =>
    update({
      media: content.media.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    })
  const setButton = (index: number, patch: Partial<PostButton>) =>
    update({
      buttons: content.buttons.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    })

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
      <div className="min-w-0 space-y-5">
        <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest">
          <div className="flex flex-wrap items-center gap-0.5 border-b border-outline-variant bg-surface-container-low px-2 py-1.5">
            {tools.map((tool) => (
              <Tool key={tool.label} {...tool} />
            ))}
            <span
              className={clsx(
                'tabular ml-auto pr-2 text-xs',
                length > limit ? 'font-semibold text-destructive' : 'text-outline',
              )}
            >
              {length} / {limit}
            </span>
          </div>
          <EditorContent editor={editor} />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Формат" isGroup>
            <Segmented
              label="Формат поста"
              value={content.format}
              onChange={(format) => update({ format })}
              options={FORMATS}
            />
          </Field>
          <div className="flex flex-col justify-end gap-3">
            <label className="flex items-center justify-between gap-3 text-sm">
              Без звука
              <Toggle
                checked={content.silent}
                onChange={(silent) => update({ silent })}
                label="Без звука"
              />
            </label>
            <label className="flex items-center justify-between gap-3 text-sm">
              Подпись над картинкой
              <Toggle
                checked={content.caption_above_media}
                onChange={(caption_above_media) => update({ caption_above_media })}
                label="Подпись над картинкой"
              />
            </label>
          </div>
        </div>

        <Field label="Картинки и видео" hint="до 10, по ссылке" isGroup>
          <div className="space-y-2">
            {content.media.map((item, index) => (
              <div key={index} className="flex gap-2">
                <SelectField
                  value={item.kind}
                  onChange={(value) => setMedia(index, { kind: value as Media['kind'] })}
                  className="w-28 shrink-0"
                  label="Тип"
                  options={MEDIA_KINDS}
                />
                <input
                  value={item.url}
                  onChange={(event) => setMedia(index, { url: event.target.value })}
                  className={cn(INPUT_CLASS, 'min-w-0 flex-1')}
                  placeholder="https://…"
                  aria-label="Адрес"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Убрать"
                  icon={<Trash2 size={15} />}
                  onClick={() =>
                    update({
                      media: content.media.filter((_, i) => i !== index),
                    })
                  }
                />
              </div>
            ))}
            {content.media.length < 10 && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Plus size={15} />}
                onClick={() =>
                  update({
                    media: [...content.media, { kind: 'photo', url: '' }],
                  })
                }
              >
                Добавить
              </Button>
            )}
          </div>
        </Field>

        <Field label="Кнопки под постом" hint="до 4" isGroup>
          <div className="space-y-2">
            {content.buttons.map((item, index) => (
              <div key={index} className="flex gap-2">
                <input
                  value={item.text}
                  onChange={(event) => setButton(index, { text: event.target.value })}
                  className={cn(INPUT_CLASS, 'w-32 shrink-0 sm:w-44')}
                  placeholder="Текст"
                  aria-label="Текст кнопки"
                />
                <input
                  value={item.url}
                  onChange={(event) => setButton(index, { url: event.target.value })}
                  className={cn(INPUT_CLASS, 'min-w-0 flex-1')}
                  placeholder="https://…"
                  aria-label="Ссылка кнопки"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Убрать"
                  icon={<Trash2 size={15} />}
                  onClick={() =>
                    update({
                      buttons: content.buttons.filter((_, i) => i !== index),
                    })
                  }
                />
              </div>
            ))}
            {content.buttons.length < 4 && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Plus size={15} />}
                onClick={() =>
                  update({
                    buttons: [...content.buttons, { text: '', url: 'https://' }],
                  })
                }
              >
                Добавить кнопку
              </Button>
            )}
          </div>
        </Field>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button
            variant="primary"
            isBusy={isBusy}
            disabled={length > limit}
            onClick={() => onSave(cleaned(content), true)}
          >
            Поставить в очередь
          </Button>
          <Button
            variant="tonal"
            disabled={isBusy || length > limit}
            onClick={() => onSave(cleaned(content), false)}
          >
            Сохранить черновик
          </Button>
          <Button variant="ghost" onClick={onCancel}>
            Отмена
          </Button>
        </div>
      </div>

      <div className="lg:sticky lg:top-6 lg:self-start">
        <p className="mb-2 px-1 text-xs font-medium tracking-wide text-outline uppercase">
          Так увидят подписчики
        </p>
        <TelegramPreview content={cleaned(content)} channel={channel} />
      </div>
    </div>
  )
}

/** Empty rows the reader added and did not fill are not sent. */
function cleaned(content: PostContent): PostContent {
  return {
    ...content,
    media: content.media.filter((item) => /^https?:\/\/\S+$/.test(item.url.trim())),
    buttons: content.buttons.filter(
      (item) => item.text.trim() && /^https?:\/\/\S+$/.test(item.url.trim()),
    ),
  }
}
