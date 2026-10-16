import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Me, Resume } from '../lib/api'
import { makeAvatar, makeMe, makeMeta, makeResume, makeResumeFacts } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { AccountPage } from './AccountPage'

/** The account as the server holds it; sign-out and deletion end the session. */
function serveAccount({ me = makeMe(), resume = null }: { me?: Me; resume?: Resume | null } = {}) {
  let current: Me | null = me
  let stored = resume
  const sent: { deletions: unknown[]; avatars: { type: string | null; bytes: number }[] } = {
    deletions: [],
    avatars: [],
  }
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(current)),
    http.get(apiUrl('/resume'), () => HttpResponse.json(stored)),
    http.get(apiUrl('/mcp/keys'), () => HttpResponse.json([])),
    http.post(apiUrl('/auth/logout'), () => {
      current = null
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(apiUrl('/auth/me/delete'), async ({ request }) => {
      sent.deletions.push(await request.json())
      current = null
      return new HttpResponse(null, { status: 204 })
    }),
    http.put(apiUrl('/auth/me/avatar'), async ({ request }) => {
      sent.avatars.push({
        type: request.headers.get('content-type'),
        bytes: (await request.arrayBuffer()).byteLength,
      })
      return HttpResponse.json(makeAvatar())
    }),
    http.delete(apiUrl('/auth/me/avatar'), () => new HttpResponse(null, { status: 204 })),
    http.delete(apiUrl('/resume'), () => {
      stored = null
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return sent
}

async function renderPage() {
  const view = renderWithProviders(<AccountPage />)
  await screen.findByRole('heading', { name: 'Аккаунт' })
  // The resume card is the last part of the page to load.
  await screen.findByRole('heading', { name: 'Резюме' })
  return view
}

const avatarInput = (container: HTMLElement) =>
  container.querySelector('input[accept^="image/"]') as HTMLInputElement

describe('AccountPage', () => {
  it('tells a member which company and team the account belongs to', async () => {
    serveAccount({
      me: makeMe({
        company: {
          company: 'Энергосеть',
          team: 'SOC',
          role: 'member',
          job_title: 'Инженер SOC',
          manager: 'Олег Смирнов',
        },
      }),
    })
    await renderPage()

    const card = screen.getByRole('heading', { name: 'Компания' }).parentElement as HTMLElement
    expect(within(card).getByText('Энергосеть')).toBeInTheDocument()
    expect(within(card).getByText('SOC')).toBeInTheDocument()
    expect(within(card).getByText('Инженер SOC')).toBeInTheDocument()
    expect(within(card).getByText('Олег Смирнов')).toBeInTheDocument()
  })

  it('leads the manager of a space to it', async () => {
    serveAccount({
      me: makeMe({
        company: {
          company: 'Энергосеть',
          team: null,
          role: 'owner',
          job_title: null,
          manager: null,
        },
      }),
    })
    await renderPage()

    expect(screen.getByRole('link', { name: 'Открыть пространство' })).toHaveAttribute(
      'href',
      '/company',
    )
  })

  it('leaves the look of the feed to the feed page, beside its tabs', async () => {
    serveAccount()
    await renderPage()

    expect(screen.queryByRole('radiogroup', { name: 'Вид ленты' })).toBeNull()
    expect(screen.queryByRole('radio', { name: /Посты/ })).toBeNull()
  })

  it('opens the introduction again on demand, for a reader and a guest alike', async () => {
    const marked: string[] = []
    server.use(
      http.post(apiUrl('/auth/me/onboarded'), ({ request }) => {
        marked.push(request.url)
        return HttpResponse.json({ onboarded_at: '2026-10-15T09:00:00Z' })
      }),
    )
    for (const me of [makeMe(), makeMe({ is_demo: true, display_name: 'Гость' })]) {
      serveAccount({ me })
      const { user, unmount } = await renderPage()

      await user.click(screen.getByRole('link', { name: 'Пройти знакомство ещё раз' }))

      expect(screen.getByTestId('location')).toHaveTextContent('/start')
      unmount()
    }
    // Opening it changes nothing on the server: only a finished or skipped one does.
    expect(marked).toEqual([])
  })

  describe('signing out', () => {
    it('signs a reader with a password out at once and remembers it was on purpose', async () => {
      serveAccount()
      const { user } = await renderPage()
      expect(screen.getByText('analyst@example.ru')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Выйти' }))

      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Аккаунт' })).toBeNull())
      // With the flag, no guest account is made behind the reader's back.
      expect(sessionStorage.getItem('radar-signed-out')).toBe('1')
    })

    it('asks a guest first: a temporary account cannot be opened again', async () => {
      serveAccount({ me: makeMe({ is_demo: true }) })
      const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
      const { user } = await renderPage()

      await user.click(screen.getByRole('button', { name: 'Выйти' }))
      expect(confirm).toHaveBeenCalledWith(
        expect.stringContaining('Войти во временный аккаунт повторно нельзя'),
      )
      expect(screen.getByRole('heading', { name: 'Аккаунт' })).toBeInTheDocument()

      confirm.mockReturnValueOnce(true)
      await user.click(screen.getByRole('button', { name: 'Выйти' }))

      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Аккаунт' })).toBeNull())
    })
  })

  describe('deleting the account', () => {
    it('asks for the password, shows a refusal, and ends the session once deleted', async () => {
      const sent = serveAccount()
      server.use(
        http.post(
          apiUrl('/auth/me/delete'),
          () => HttpResponse.json({ detail: 'Неверный пароль' }, { status: 403 }),
          { once: true },
        ),
      )
      const { user } = await renderPage()

      await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }))
      await user.type(screen.getByLabelText('Пароль для подтверждения'), 'не тот')
      await user.click(screen.getByRole('button', { name: 'Удалить навсегда' }))
      expect(await screen.findByText('Неверный пароль')).toBeInTheDocument()

      await user.clear(screen.getByLabelText('Пароль для подтверждения'))
      await user.type(screen.getByLabelText('Пароль для подтверждения'), 'верный пароль')
      await user.click(screen.getByRole('button', { name: 'Удалить навсегда' }))

      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Аккаунт' })).toBeNull())
      expect(sent.deletions).toEqual([{ password: 'верный пароль' }])
    })

    it('hides the password form again on "Отмена"', async () => {
      serveAccount()
      const { user } = await renderPage()

      await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }))
      await user.click(screen.getByRole('button', { name: 'Отмена' }))

      expect(screen.queryByLabelText('Пароль для подтверждения')).toBeNull()
      expect(screen.getByRole('button', { name: 'Удалить аккаунт' })).toBeInTheDocument()
    })

    it('deletes a guest account without a password and offers to register instead', async () => {
      const sent = serveAccount({ me: makeMe({ is_demo: true }) })
      const { user } = await renderPage()
      expect(screen.getByText('Без почты и пароля')).toBeInTheDocument()
      expect(screen.getByText('временный')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Зарегистрироваться' })).toHaveAttribute(
        'href',
        '/register',
      )

      await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }))

      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Аккаунт' })).toBeNull())
      expect(sent.deletions).toEqual([{ password: '' }])
    })
  })

  describe('the photo', () => {
    it('refuses a picture over 5 MB without uploading it', async () => {
      const sent = serveAccount()
      const { user, container } = await renderPage()

      await user.upload(
        avatarInput(container),
        new File([new Uint8Array(5_000_001)], 'big.jpg', { type: 'image/jpeg' }),
      )

      expect(
        await screen.findByText('Размер файла превышает 5 МБ. Выберите изображение поменьше.'),
      ).toBeInTheDocument()
      expect(sent.avatars).toEqual([])
    })

    it('uploads a new picture and removes it', async () => {
      const sent = serveAccount()
      const { user, container } = await renderPage()

      await user.upload(
        avatarInput(container),
        new File([new Uint8Array(2_048)], 'me.png', { type: 'image/png' }),
      )

      expect(await screen.findByText('Фото обновлено')).toBeInTheDocument()
      expect(sent.avatars).toEqual([{ type: 'image/png', bytes: 2_048 }])
      await user.click(screen.getByRole('button', { name: 'Удалить фото' }))

      expect(await screen.findByText('Фото убрано')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Удалить фото' })).toBeNull()
      expect(screen.getAllByRole('button', { name: 'Загрузить фото' })).toHaveLength(2)
    })

    it('shows why the server refused a picture', async () => {
      serveAccount()
      server.use(
        http.put(apiUrl('/auth/me/avatar'), () =>
          HttpResponse.json({ detail: 'Это не изображение' }, { status: 422 }),
        ),
      )
      const { user, container } = await renderPage()

      await user.upload(avatarInput(container), new File(['%PDF'], 'me.png', { type: 'image/png' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Это не изображение')
    })

    it('offers the nine ready pictures with the current one pressed, and picks another', async () => {
      serveAccount({ me: makeMe({ avatar_preset: 'teal' }) })
      const picked: unknown[] = []
      server.use(
        http.put(apiUrl('/auth/me/avatar-preset'), async ({ request }) => {
          picked.push(await request.json())
          return HttpResponse.json({ avatar_url: null, avatar_preset: 'orange' })
        }),
      )
      const { user } = await renderPage()
      const pictures = screen.getByRole('group', { name: 'Картинка профиля' })
      const presets = within(pictures)
        .getAllByRole('button')
        .filter((button) => button.hasAttribute('aria-pressed'))

      expect(presets).toHaveLength(9)
      expect(within(pictures).getByRole('button', { name: 'Бирюзовый' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      // The chosen one is not sent again.
      await user.click(within(pictures).getByRole('button', { name: 'Бирюзовый' }))
      await user.click(within(pictures).getByRole('button', { name: 'Оранжевый' }))

      expect(await screen.findByText('Картинка обновлена')).toBeInTheDocument()
      expect(picked).toEqual([{ preset: 'orange' }])
      expect(within(pictures).getByRole('button', { name: 'Оранжевый' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(within(pictures).getByRole('button', { name: 'Бирюзовый' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
    })

    it('keeps an uploaded photo beside the ready pictures until one of them replaces it', async () => {
      serveAccount({ me: makeMe({ avatar_url: '/api/v1/auth/me/avatar?v=1' }) })
      server.use(
        http.put(apiUrl('/auth/me/avatar-preset'), () =>
          HttpResponse.json({ avatar_url: null, avatar_preset: 'grey' }),
        ),
      )
      const { user } = await renderPage()
      const pictures = screen.getByRole('group', { name: 'Картинка профиля' })

      // The photo is what is shown: none of the ready pictures is pressed.
      expect(within(pictures).getByRole('button', { name: 'Сменить фото' })).toBeInTheDocument()
      expect(within(pictures).queryAllByRole('button', { pressed: true })).toEqual([])
      expect(screen.getByRole('button', { name: 'Удалить фото' })).toBeInTheDocument()

      await user.click(within(pictures).getByRole('button', { name: 'Серый' }))

      await waitFor(() =>
        expect(within(pictures).getByRole('button', { name: 'Серый' })).toHaveAttribute(
          'aria-pressed',
          'true',
        ),
      )
      expect(within(pictures).getByRole('button', { name: 'Загрузить фото' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Удалить фото' })).toBeNull()
    })
  })

  it('tells who is in a shared account and offers no way to delete it', async () => {
    serveAccount({
      me: makeMe({ is_shared: true, email: 'reader@radar.local', display_name: 'Читатель' }),
    })
    await renderPage()

    expect(screen.getByText('Общий аккаунт без пароля')).toBeInTheDocument()
    expect(screen.getByText('общий')).toBeInTheDocument()
    expect(screen.queryByText('reader@radar.local')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Общий аккаунт' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Удалить аккаунт' })).toBeNull()
  })

  describe('the resume', () => {
    it('shows what was read from the resume, with the rest of the skills on demand', async () => {
      const skills = Array.from({ length: 16 }, (_, index) => `Навык ${index + 1}`)
      serveAccount({ resume: makeResume({ facts: makeResumeFacts({ skills }) }) })
      const { user } = await renderPage()

      expect(
        await screen.findByText('Ведущий инженер по защите АСУ ТП в электроэнергетике'),
      ).toBeInTheDocument()
      expect(screen.getByText('ведущий специалист')).toBeInTheDocument()
      expect(
        screen.getByText('PDF · встроенный разбор · разобрано языковой моделью'),
      ).toBeInTheDocument()
      expect(screen.getByText('Навык 14')).toBeInTheDocument()
      expect(screen.queryByText('Навык 15')).toBeNull()

      await user.click(screen.getByRole('button', { name: 'ещё 2' }))

      expect(screen.getByText('Навык 16')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /^ещё/ })).toBeNull()
      expect(screen.getByRole('link', { name: 'Создать профиль по резюме' })).toHaveAttribute(
        'href',
        '/welcome',
      )
    })

    it('deletes the data read from the resume once the reader confirms', async () => {
      serveAccount({ resume: makeResume() })
      const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
      const { user } = await renderPage()

      await user.click(await screen.findByRole('button', { name: 'Удалить данные' }))
      expect(confirm).toHaveBeenCalledWith('Удалить все данные из резюме?')
      expect(screen.getByRole('button', { name: 'Удалить данные' })).toBeInTheDocument()

      confirm.mockReturnValueOnce(true)
      await user.click(screen.getByRole('button', { name: 'Удалить данные' }))

      expect(
        await screen.findByRole('button', { name: /Перетащите резюме сюда/ }),
      ).toBeInTheDocument()
      expect(screen.queryByText('ведущий специалист')).toBeNull()
    })

    it('says the resume is being read, and how long it takes with the model', async () => {
      server.use(
        http.get(apiUrl('/meta'), () =>
          HttpResponse.json(makeMeta({ llm_provider: 'ollama', resume_parser: 'docling' })),
        ),
      )
      serveAccount({
        resume: makeResume({
          status: 'processing',
          facts: null,
          suggestion: null,
          created_at: new Date().toISOString(),
        }),
      })
      renderWithProviders(<AccountPage />)

      expect(await screen.findByRole('status', { name: 'Читаем резюме' })).toBeInTheDocument()
      expect(
        await screen.findByText(/Разбираем структуру документа,.*10–30 секунд/),
      ).toBeInTheDocument()
    })

    it('stops waiting for a resume read for over five minutes and offers another upload', async () => {
      serveAccount({
        resume: makeResume({
          status: 'processing',
          facts: null,
          suggestion: null,
          created_at: new Date(Date.now() - 6 * 60_000).toISOString(),
        }),
      })
      await renderPage()

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Резюме разбирается дольше обычного',
      )
      expect(screen.getByRole('button', { name: /Перетащите резюме сюда/ })).toBeEnabled()
      expect(screen.queryByRole('status', { name: 'Читаем резюме' })).toBeNull()
    })

    it('shows why the resume could not be read', async () => {
      serveAccount({
        resume: makeResume({
          status: 'failed',
          error: 'В файле нет текста',
          facts: null,
          suggestion: null,
        }),
      })
      await renderPage()

      expect(await screen.findByRole('alert')).toHaveTextContent('В файле нет текста')
    })

    it('replaces a resume already read and waits for the new one', async () => {
      let name: string | null = null
      serveAccount({ resume: makeResume() })
      server.use(
        http.post(apiUrl('/resume'), ({ request }) => {
          name = decodeURIComponent(request.headers.get('x-file-name') ?? '')
          return HttpResponse.json(
            makeResume({
              status: 'processing',
              facts: null,
              suggestion: null,
              created_at: new Date().toISOString(),
            }),
          )
        }),
      )
      const { user, container } = await renderPage()
      await screen.findByRole('button', { name: /Заменить резюме/ })
      const input = container.querySelector(
        'input[accept=".pdf,.docx,.txt,.md"]',
      ) as HTMLInputElement

      await user.upload(input, new File(['Инженер АСУ ТП'], 'Новое резюме.docx'))

      expect(await screen.findByRole('status', { name: 'Читаем резюме' })).toBeInTheDocument()
      expect(name).toBe('Новое резюме.docx')
    })
  })
})
