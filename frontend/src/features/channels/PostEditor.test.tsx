import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeMedia, makePostButton, makePostContent } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import type { PostContent } from '../../lib/publishing'
import { PostEditor } from './PostEditor'

function renderEditor(initial: Partial<PostContent> = {}, { isBusy = false } = {}) {
  const onSave = vi.fn<(content: PostContent, approve: boolean) => void>()
  const onCancel = vi.fn()
  const view = renderWithProviders(
    <PostEditor
      initial={makePostContent({ html: '<p>Текст поста</p>', ...initial })}
      channel="Энергетика и ИБ"
      isBusy={isBusy}
      onSave={onSave}
      onCancel={onCancel}
    />,
  )
  return { ...view, onSave, onCancel }
}

/** Selects the whole text of the post, as a reader does before a toolbar button. */
async function selectAll(user: ReturnType<typeof renderEditor>['user']) {
  await user.click(await screen.findByRole('textbox'))
  await user.keyboard('{Control>}a{/Control}')
}

/** Puts text at the end of a field at once: typing it key by key re-renders the editor each time. */
async function typeInto(
  user: ReturnType<typeof renderEditor>['user'],
  field: HTMLElement,
  text: string,
) {
  await user.click(field)
  await user.paste(text)
}

const saveDraft = () => screen.getByRole('button', { name: 'Сохранить черновик' })
const queue = () => screen.getByRole('button', { name: 'Поставить в очередь' })
const savedContent = (onSave: ReturnType<typeof renderEditor>['onSave']) => onSave.mock.calls[0][0]

describe('PostEditor', () => {
  it('formats the selected text from the toolbar and marks the active button', async () => {
    const { user, onSave } = renderEditor()
    await selectAll(user)

    await user.click(screen.getByRole('button', { name: 'Жирный' }))
    await user.click(screen.getByRole('button', { name: 'Скрытый текст' }))

    expect(screen.getByRole('button', { name: 'Жирный' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Курсив' })).toHaveAttribute('aria-pressed', 'false')
    await user.click(saveDraft())
    expect(savedContent(onSave).html).toBe(
      '<p><strong><tg-spoiler>Текст поста</tg-spoiler></strong></p>',
    )
  })

  it('turns the text into a numbered list', async () => {
    const { user, onSave } = renderEditor()
    await selectAll(user)

    await user.click(screen.getByRole('button', { name: 'Нумерованный список' }))
    await user.click(saveDraft())
    expect(savedContent(onSave).html).toContain('<ol><li><p>Текст поста</p></li></ol>')
  })

  it('links the selected text to the address typed in the prompt', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('https://cert.example.org/b-12')
    const { user, onSave } = renderEditor()
    await selectAll(user)

    await user.click(screen.getByRole('button', { name: 'Ссылка' }))
    await user.click(saveDraft())

    expect(prompt).toHaveBeenCalledWith('Ссылка (https://…)', 'https://')
    expect(savedContent(onSave).html).toContain('href="https://cert.example.org/b-12"')
    expect(
      within(screen.getByRole('article')).getByRole('link', { name: 'Текст поста' }),
    ).toHaveAttribute('href', 'https://cert.example.org/b-12')
  })

  it('offers the current address of a link, and removes the link when it is erased', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('')
    const { user, onSave } = renderEditor({
      html: '<p><a href="https://cert.example.org/b-12">Бюллетень</a></p>',
    })
    await selectAll(user)

    await user.click(screen.getByRole('button', { name: 'Ссылка' }))
    await user.click(saveDraft())

    expect(prompt).toHaveBeenCalledWith('Ссылка (https://…)', 'https://cert.example.org/b-12')
    expect(savedContent(onSave).html).toBe('<p>Бюллетень</p>')
  })

  it('keeps the text as it was when the prompt is cancelled or the address could run code', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValueOnce(null)
    const { user, onSave } = renderEditor()
    await selectAll(user)

    await user.click(screen.getByRole('button', { name: 'Ссылка' }))
    prompt.mockReturnValueOnce('javascript:alert(1)')
    await user.click(screen.getByRole('button', { name: 'Ссылка' }))
    await user.click(saveDraft())

    expect(prompt).toHaveBeenCalledTimes(2)
    expect(savedContent(onSave).html).toBe('<p>Текст поста</p>')
  })

  it('counts against the caption limit with one picture and blocks saving over it', async () => {
    const { user, onSave } = renderEditor({
      html: `<p>${'а'.repeat(1025)}</p>`,
      media: [makeMedia()],
    })

    expect(await screen.findByText('1025 / 1024')).toBeInTheDocument()
    expect(queue()).toBeDisabled()
    expect(saveDraft()).toBeDisabled()

    // Without the picture the post is a message, with Telegram's 4096 characters.
    await user.click(screen.getByRole('button', { name: 'Убрать' }))

    expect(screen.getByText('1025 / 4096')).toBeInTheDocument()
    await user.click(queue())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ media: [] }), true)
  })

  it('blocks a message over 4096 characters until it becomes a rich post', async () => {
    const { user, onSave } = renderEditor({ html: `<p>${'а'.repeat(4097)}</p>` })

    expect(await screen.findByText('4097 / 4096')).toBeInTheDocument()
    expect(saveDraft()).toBeDisabled()

    await user.click(screen.getByRole('radio', { name: /Rich-пост/ }))

    expect(screen.getByText('4097 / 32768')).toBeInTheDocument()
    await user.click(saveDraft())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ format: 'rich' }), false)
  })

  it('does not count an added picture row that is still empty against the caption limit', async () => {
    const { user, onSave } = renderEditor({ html: `<p>${'а'.repeat(2000)}</p>` })

    await user.click(await screen.findByRole('button', { name: 'Добавить' }))

    expect(screen.getByRole('textbox', { name: 'Адрес' })).toHaveValue('')
    expect(screen.getByText('2000 / 4096')).toBeInTheDocument()
    await user.click(saveDraft())
    expect(savedContent(onSave).media).toEqual([])
  })

  it('sends the pictures and buttons the reader filled in, and drops the rows left unfinished', async () => {
    const { user, onSave } = renderEditor()

    await user.click(await screen.findByRole('button', { name: 'Добавить' }))
    await user.click(screen.getByRole('button', { name: 'Добавить' }))
    const [first] = screen.getAllByRole('textbox', { name: 'Адрес' })
    await typeInto(user, first, 'https://cdn.example.org/clip.mp4')
    await user.click(screen.getAllByRole('button', { name: /Тип: Фото/ })[0])
    await user.click(
      within(await screen.findByRole('listbox')).getByRole('option', { name: 'Видео' }),
    )

    await user.click(screen.getByRole('button', { name: 'Добавить кнопку' }))
    await user.click(screen.getByRole('button', { name: 'Добавить кнопку' }))
    const [label] = screen.getAllByRole('textbox', { name: 'Текст кнопки' })
    const [link, linkWithoutText] = screen.getAllByRole('textbox', { name: 'Ссылка кнопки' })
    await typeInto(user, label, 'Бюллетень')
    await typeInto(user, link, 'cert.example.org/b-12')
    // A button without words cannot be sent: Telegram refuses it.
    await typeInto(user, linkWithoutText, 'cert.example.org/b-13')

    await user.click(queue())

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        media: [{ kind: 'video', url: 'https://cdn.example.org/clip.mp4' }],
        buttons: [{ text: 'Бюллетень', url: 'https://cert.example.org/b-12' }],
      }),
      true,
    )
  })

  it('stops offering rows at 10 pictures and 4 buttons, and removes the row asked', async () => {
    const { user, onSave } = renderEditor({
      media: Array.from({ length: 10 }, (_, index) =>
        makeMedia({ url: `https://cdn.example.org/${index}.jpg` }),
      ),
      buttons: ['Один', 'Два', 'Три', 'Четыре'].map((text) => makePostButton({ text })),
    })

    expect(await screen.findAllByRole('textbox', { name: 'Адрес' })).toHaveLength(10)
    expect(screen.queryByRole('button', { name: 'Добавить' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Добавить кнопку' })).toBeNull()

    // Media rows come first: the eleventh "Убрать" belongs to the second button.
    await user.click(screen.getAllByRole('button', { name: 'Убрать' })[11])
    await user.click(saveDraft())

    expect(savedContent(onSave).buttons.map((button) => button.text)).toEqual([
      'Один',
      'Три',
      'Четыре',
    ])
    expect(screen.getByRole('button', { name: 'Добавить кнопку' })).toBeInTheDocument()
  })

  it('sends the switches for a silent post and a caption above the picture', async () => {
    const { user, onSave } = renderEditor()

    await user.click(await screen.findByRole('switch', { name: 'Без звука' }))
    await user.click(screen.getByRole('switch', { name: 'Подпись над картинкой' }))
    await user.click(saveDraft())

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ silent: true, caption_above_media: true }),
      false,
    )
  })

  it('shows the post in the preview as subscribers will see it, without unfinished rows', async () => {
    const { user } = renderEditor()
    const preview = screen.getByRole('article')
    expect(within(preview).getByText('Текст поста')).toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Добавить' }))
    expect(within(preview).queryByRole('presentation')).toBeNull()
    await user.type(screen.getByRole('textbox', { name: 'Адрес' }), 'https://cdn.example.org/1.jpg')

    expect(within(preview).getByRole('presentation')).toHaveAttribute(
      'src',
      'https://cdn.example.org/1.jpg',
    )
  })

  it('cannot be saved twice while a save is under way, and can be left', async () => {
    const { user, onCancel } = renderEditor({}, { isBusy: true })

    expect(queue()).toBeDisabled()
    expect(saveDraft()).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Отмена' }))

    expect(onCancel).toHaveBeenCalled()
  })
})
