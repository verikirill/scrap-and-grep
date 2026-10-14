import { screen, waitFor } from '@testing-library/react'
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
