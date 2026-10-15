import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ProfileSpec, Resume } from '../lib/api'
import { makeInterests, makeProfile, makeResume, makeSpec } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { WelcomePage } from './WelcomePage'

const INTERESTS = makeInterests(3)
const SUGGESTION = makeSpec({ name: 'По резюме: защита АСУ ТП', interests: INTERESTS })

/** A resume that is still being read, uploaded just now. */
const reading = (): Resume =>
  makeResume({
    status: 'processing',
    facts: null,
    suggestion: null,
    created_at: new Date().toISOString(),
  })

function serveWelcome(resume: Resume | null) {
  const saved: ProfileSpec[] = []
  server.use(
    http.get(apiUrl('/resume'), () => HttpResponse.json(resume)),
    http.post(apiUrl('/profiles'), async ({ request }) => {
      const spec = (await request.json()) as ProfileSpec
      saved.push(spec)
      return HttpResponse.json(makeProfile({ spec }))
    }),
  )
  return saved
}

function renderWelcome() {
  return renderWithProviders(<WelcomePage />, { route: '/welcome' })
}

const create = () => screen.getByRole('button', { name: 'Создать профиль и открыть ленту' })
const topic = (title: string) => screen.getByRole('checkbox', { name: new RegExp(title) })

describe('WelcomePage', () => {
  it('greets the reader and reads the resume they upload', async () => {
    serveWelcome(null)
    let name: string | null = null
    server.use(
      http.post(apiUrl('/resume'), ({ request }) => {
        name = decodeURIComponent(request.headers.get('x-file-name') ?? '')
        return HttpResponse.json(reading())
      }),
    )
    const { user, container } = renderWelcome()
    expect(
      await screen.findByRole('heading', { name: 'Анна Петрова, расскажите о своей работе' }),
    ).toBeInTheDocument()

    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['Инженер АСУ ТП'], 'resume.pdf'),
    )

    expect(await screen.findByRole('status', { name: 'Читаем резюме' })).toBeInTheDocument()
    expect(name).toBe('resume.pdf')
  })

  it('creates the profile from the topics kept and the words changed, then opens the feed', async () => {
    const saved = serveWelcome(makeResume({ suggestion: SUGGESTION }))
    const { user } = renderWelcome()

    expect(await screen.findByText('выбрано 3 из 3')).toBeInTheDocument()
    expect(topic(INTERESTS[1].title)).toHaveAttribute('aria-checked', 'true')
    await user.click(topic(INTERESTS[1].title))
    expect(topic(INTERESTS[1].title)).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('выбрано 2 из 3')).toBeInTheDocument()

    const name = screen.getByRole('textbox', { name: 'Название профиля' })
    await user.clear(name)
    await user.type(name, 'Защита подстанций')
    await user.type(screen.getByRole('textbox', { name: /Роль читателя/ }), ', 187-ФЗ')
    fireEvent.change(screen.getByRole('slider', { name: /Размер выпуска/ }), {
      target: { value: '12' },
    })
    expect(screen.getByText('до 12 публикаций')).toBeInTheDocument()
    await user.click(create())

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/feed'))
    expect(saved).toEqual([
      {
        ...SUGGESTION,
        name: 'Защита подстанций',
        role: `${SUGGESTION.role}, 187-ФЗ`,
        max_items: 12,
        interests: [INTERESTS[0], INTERESTS[2]],
      },
    ])
  })

  it('does not create a profile without a topic or without a name', async () => {
    serveWelcome(makeResume({ suggestion: makeSpec({ interests: INTERESTS.slice(0, 1) }) }))
    const { user } = renderWelcome()

    await user.click(await screen.findByRole('checkbox', { name: new RegExp(INTERESTS[0].title) }))
    expect(create()).toBeDisabled()
    await user.click(topic(INTERESTS[0].title))
    expect(create()).toBeEnabled()

    const name = screen.getByRole('textbox', { name: 'Название профиля' })
    await user.clear(name)
    await user.type(name, ' А ')
    expect(create()).toBeDisabled()
  })

  it('shows why the profile was not saved and stays on the page', async () => {
    serveWelcome(makeResume({ suggestion: SUGGESTION }))
    server.use(
      http.post(apiUrl('/profiles'), () =>
        HttpResponse.json({ detail: 'Профилей не больше 10' }, { status: 409 }),
      ),
    )
    const { user } = renderWelcome()

    await user.click(await screen.findByRole('button', { name: 'Создать профиль и открыть ленту' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Профилей не больше 10')
    expect(screen.getByTestId('location')).toHaveTextContent('/welcome')
  })

  it('takes another file in place of a resume already read', async () => {
    serveWelcome(makeResume({ suggestion: SUGGESTION }))
    server.use(
      http.post(apiUrl('/resume'), () =>
        HttpResponse.json(
          makeResume({
            created_at: new Date().toISOString(),
            suggestion: makeSpec({ name: 'По резюме: SOC', interests: INTERESTS.slice(0, 2) }),
          }),
        ),
      ),
    )
    const { user, container } = renderWelcome()

    await user.click(await screen.findByRole('button', { name: 'Загрузить другой файл' }))
    expect(screen.queryByText('Профиль интересов')).toBeNull()
    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['Аналитик SOC'], 'soc.docx'),
    )

    // The review starts again from the new suggestion.
    expect(await screen.findByDisplayValue('По резюме: SOC')).toBeInTheDocument()
    expect(screen.getByText('выбрано 2 из 2')).toBeInTheDocument()
  })

  it('says why the resume could not be read, or that it takes too long', async () => {
    serveWelcome(
      makeResume({
        status: 'failed',
        error: 'В файле нет текста',
        facts: null,
        suggestion: null,
      }),
    )
    const { unmount } = renderWelcome()
    expect(await screen.findByRole('alert')).toHaveTextContent('В файле нет текста')
    unmount()

    serveWelcome(
      makeResume({
        status: 'processing',
        facts: null,
        suggestion: null,
        created_at: new Date(Date.now() - 6 * 60_000).toISOString(),
      }),
    )
    renderWelcome()

    expect(await screen.findByRole('alert')).toHaveTextContent('Резюме разбирается дольше обычного')
    expect(screen.getByRole('button', { name: /Перетащите резюме сюда/ })).toBeEnabled()
  })

  it('shows why the upload was refused', async () => {
    serveWelcome(null)
    server.use(
      http.post(apiUrl('/resume'), () =>
        HttpResponse.json({ detail: 'Файл повреждён' }, { status: 422 }),
      ),
    )
    const { user, container } = renderWelcome()
    await screen.findByRole('heading', { name: /расскажите о своей работе/ })

    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['?'], 'resume.pdf'),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Файл повреждён')
    expect(
      within(screen.getByRole('button', { name: /Перетащите резюме сюда/ })).getByText(
        'Перетащите резюме сюда',
      ),
    ).toBeInTheDocument()
  })
})
