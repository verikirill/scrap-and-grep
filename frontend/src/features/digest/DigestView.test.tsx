import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_BASE } from '../../lib/api'
import type { Me, Settings } from '../../lib/api'
import { makeDigest, makeItem, makeMailState, makeMe, makeTopic } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { DigestView } from './DigestView'

/** The account as the server keeps it: settings sent are there on the next read. */
function serveAccount(initial: Me) {
  let me = initial
  const patches: Partial<Settings>[] = []
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(me)),
    http.patch(apiUrl('/auth/me/settings'), async ({ request }) => {
      const patch = (await request.json()) as Partial<Settings>
      patches.push(patch)
      me = { ...me, ...patch }
      return HttpResponse.json({
        feed_view: me.feed_view,
        feed_order: me.feed_order,
        folded_sections: me.folded_sections ?? [],
      })
    }),
  )
  return patches
}

const vulnerabilities = makeTopic({
  title: 'Уязвимости',
  items: [
    makeItem({ headline: 'Siemens закрыла уязвимость', priority: 'high', ours: ['Siemens'] }),
    makeItem({ headline: 'Патч для SCADA', priority: 'high' }),
    makeItem({ headline: 'Обзор недели', priority: 'low' }),
  ],
})
const attacks = makeTopic({
  title: 'Атаки',
  items: [makeItem({ headline: 'Атака на подстанцию' })],
})

beforeEach(() => {
  server.use(
    http.get(apiUrl('/reactions'), () => HttpResponse.json({})),
    http.get(apiUrl('/digests/:id/mail'), () =>
      HttpResponse.json(makeMailState({ available: false })),
    ),
  )
})

describe('DigestView sections', () => {
  it('folds a section by its heading, keeps it with the account and says what is inside', async () => {
    const patches = serveAccount(makeMe())
    const { user } = renderWithProviders(
      <DigestView digest={makeDigest({ topics: [vulnerabilities, attacks] })} />,
    )
    const heading = await screen.findByRole('button', { name: /Уязвимости/ })
    expect(heading).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Патч для SCADA' })).toBeInTheDocument()

    await user.click(heading)

    await waitFor(() => expect(heading).toHaveAttribute('aria-expanded', 'false'))
    expect(screen.queryByRole('link', { name: 'Патч для SCADA' })).toBeNull()
    // Folded, the heading still tells the urgent and the reader's own entries.
    expect(within(heading).getByText('2 высокий')).toBeInTheDocument()
    expect(within(heading).getByText('касается нас: 1')).toBeInTheDocument()
    expect(patches).toEqual([{ folded_sections: ['Уязвимости'] }])
    // The other section is untouched.
    expect(screen.getByRole('link', { name: 'Атака на подстанцию' })).toBeInTheDocument()
  })

  it('opens a section folded in an earlier issue and forgets the fold', async () => {
    const patches = serveAccount(makeMe({ folded_sections: ['Атаки', 'Уязвимости'] }))
    const { user } = renderWithProviders(
      <DigestView digest={makeDigest({ topics: [vulnerabilities, attacks] })} />,
    )
    const heading = await screen.findByRole('button', { name: /Уязвимости/ })
    await waitFor(() => expect(heading).toHaveAttribute('aria-expanded', 'false'))

    await user.click(heading)

    expect(await screen.findByRole('link', { name: 'Патч для SCADA' })).toBeInTheDocument()
    expect(patches).toEqual([{ folded_sections: ['Атаки'] }])
  })

  it('puts the fold back when the server refuses to keep it, even if the account cannot be re-read', async () => {
    const unavailable = () => HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 })
    server.use(
      // The account is read once; after the refusal it cannot be read again,
      // so only the client's own rollback can restore the section.
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe()), { once: true }),
      http.get(apiUrl('/auth/me'), unavailable),
      http.patch(apiUrl('/auth/me/settings'), unavailable),
    )
    const { user } = renderWithProviders(<DigestView digest={makeDigest({ topics: [attacks] })} />)
    const heading = await screen.findByRole('button', { name: /Атаки/ })

    await user.click(heading)

    await waitFor(() => expect(heading).toHaveAttribute('aria-expanded', 'true'))
    expect(screen.getByRole('link', { name: 'Атака на подстанцию' })).toBeInTheDocument()
  })

  it('shows five entries of a long section and the rest on request', async () => {
    const items = Array.from({ length: 8 }, (_, index) =>
      makeItem({ headline: `Запись ${index + 1}` }),
    )
    const { user } = renderWithProviders(
      <DigestView digest={makeDigest({ topics: [makeTopic({ title: 'Новости', items })] })} />,
    )
    expect(await screen.findByRole('link', { name: 'Запись 5' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Запись 6' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Ещё 3 записи' }))

    expect(screen.getByRole('link', { name: 'Запись 8' })).toBeInTheDocument()
  })
})

describe('DigestView jumps', () => {
  // jsdom has no Web Animations: the blink of the entry jumped to is a stub here.
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, 'animate', {
      configurable: true,
      value: vi.fn(),
    })
  })
  afterEach(() => {
    Reflect.deleteProperty(HTMLElement.prototype, 'animate')
  })

  it('opens a folded section for a jump from the risk matrix to one of its entries', async () => {
    serveAccount(makeMe({ folded_sections: ['Уязвимости'] }))
    const flaw = makeItem({
      headline: 'RCE в FortiMail',
      kind: 'vulnerability',
      ours: ['FortiMail'],
      vulnerability: {
        ids: ['CVE-2026-1001'],
        name: 'FortiMail',
        cvss_score: '9.8',
        exploit: 'none',
      },
    })
    const { user } = renderWithProviders(
      <DigestView
        digest={makeDigest({ topics: [makeTopic({ title: 'Уязвимости', items: [flaw] })] })}
      />,
    )
    const heading = await screen.findByRole('button', { name: /Уязвимости/ })
    await waitFor(() => expect(heading).toHaveAttribute('aria-expanded', 'false'))

    await user.click(screen.getByRole('button', { name: 'Открыть запись 1: RCE в FortiMail' }))

    const entry = await screen.findByRole('link', { name: 'RCE в FortiMail' })
    expect(heading).toHaveAttribute('aria-expanded', 'true')
    // Once the section has drawn, the entry is scrolled to and blinks.
    const article = entry.closest('article')!
    await waitFor(() => expect(HTMLElement.prototype.animate).toHaveBeenCalled())
    expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(article)
  })
})

describe('DigestView header', () => {
  it('counts the funnel from the period to the issue and states the models', async () => {
    renderWithProviders(
      <DigestView
        digest={makeDigest({
          stats: {
            window_total: 1240,
            candidates: 40,
            selected: 12,
            sources: 9,
            llm: 'gpt-oss:120b',
            duplicates_merged: 3,
          },
        })}
      />,
    )
    // Three small chips in one line, no bars.
    const funnel = await screen.findByRole('list', { name: 'Цифры выпуска' })
    const steps = within(funnel).getAllByRole('listitem')
    expect(steps).toHaveLength(3)
    expect(steps[0]).toHaveTextContent(/^1\s240публикаций за период$/)
    expect(steps[1]).toHaveTextContent(/^40кандидатов по интересам$/)
    expect(steps[2]).toHaveTextContent(/^12в выпуске$/)
    expect(screen.getByText(/9 источников · объединено повторов: 3/)).toBeInTheDocument()
    expect(screen.queryByText(/Модель была частично недоступна/)).toBeNull()
  })

  it('says how much the fallback did when the model was partly unavailable', async () => {
    renderWithProviders(
      <DigestView
        digest={makeDigest({
          stats: {
            window_total: 300,
            candidates: 40,
            selected: 12,
            degraded: true,
            graded_by_model: 25,
            written_by_model: 7,
          },
        })}
      />,
    )
    expect(
      await screen.findByText(
        'Модель была частично недоступна: оценила 25 из 40 кандидатов и составила 7 из 12 записей. Остальное обработал резервный алгоритм.',
      ),
    ).toBeInTheDocument()
  })

  it('exports the issue as Markdown and DOCX and compares it with the previous one', async () => {
    const { rerender } = renderWithProviders(
      <DigestView digest={makeDigest({ id: 'digest-2' })} previousId="digest-1" />,
    )
    expect(await screen.findByRole('link', { name: 'Markdown' })).toHaveAttribute(
      'href',
      `${API_BASE}/digests/digest-2/export.md`,
    )
    expect(screen.getByRole('link', { name: 'DOCX' })).toHaveAttribute(
      'href',
      `${API_BASE}/digests/digest-2/export.docx`,
    )
    expect(screen.getByRole('link', { name: 'Сравнить с предыдущим' })).toHaveAttribute(
      'href',
      '/compare?base=digest-1&other=digest-2',
    )

    // The first issue of a profile has nothing to compare with.
    rerender(<DigestView digest={makeDigest({ id: 'digest-2' })} />)
    expect(screen.queryByRole('link', { name: 'Сравнить с предыдущим' })).toBeNull()
  })

  it('tells management what the issue means for them, besides the highlights', async () => {
    server.use(
      http.get(apiUrl('/digests/:id/briefing'), () =>
        HttpResponse.json({ available: false, voices: [], briefing: null }),
      ),
    )
    const digest = makeDigest({
      highlights: ['Атаки на энергетику участились'],
      implications: ['Проверить подрядчиков на фишинг'],
    })
    const { rerender } = renderWithProviders(
      <DigestView
        digest={{
          ...digest,
          audience: 'management',
          profile: { ...digest.profile, audience: 'management' },
        }}
      />,
    )
    expect(await screen.findByRole('heading', { name: 'Что это значит для нас' })).toBeVisible()
    expect(screen.getByText('Проверить подрядчиков на фишинг')).toBeInTheDocument()
    expect(screen.getByText('Атаки на энергетику участились')).toBeInTheDocument()

    // A specialist's issue keeps the highlights only.
    rerender(<DigestView digest={digest} />)
    expect(screen.getByRole('heading', { name: 'Главное' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Что это значит для нас' })).toBeNull()
    expect(screen.queryByText('Проверить подрядчиков на фишинг')).toBeNull()
  })

  it('puts the most important news before the issue’s numbers', async () => {
    renderWithProviders(
      <DigestView
        digest={makeDigest({
          highlights: ['Атаки на энергетику участились'],
          stats: { window_total: 1210, candidates: 60, selected: 15 },
        })}
      />,
    )
    const funnel = await screen.findByRole('list', { name: 'Цифры выпуска' })
    const news = screen.getByRole('heading', { name: 'Главное' })
    expect(news.compareDocumentPosition(funnel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('leaves out the blocks the reader’s profile hides and keeps the entries', async () => {
    const digest = makeDigest({
      highlights: ['Атаки на энергетику участились'],
      topics: [vulnerabilities],
      rejected: [makeItem({ title: 'Обзор рынка SIEM', reject_reason: 'low_score' })],
      stats: { window_total: 300, candidates: 40, selected: 3, sources: 9 },
    })
    const { rerender } = renderWithProviders(<DigestView digest={digest} />)
    expect(await screen.findByRole('list', { name: 'Цифры выпуска' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Не вошло в выпуск/ })).toBeInTheDocument()
    expect(screen.getByText(/9 источников/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Вопрос к выпуску' })).toBeInTheDocument()

    rerender(
      <DigestView
        digest={{ ...digest, hidden_digest_blocks: ['funnel', 'rejected', 'method', 'ask'] }}
      />,
    )

    expect(screen.queryByRole('list', { name: 'Цифры выпуска' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Не вошло в выпуск/ })).toBeNull()
    expect(screen.queryByText(/9 источников/)).toBeNull()
    expect(screen.queryByRole('textbox', { name: 'Вопрос к выпуску' })).toBeNull()
    // The entries and "Главное" always stay.
    expect(screen.getByRole('heading', { name: 'Главное' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Siemens закрыла уязвимость' })).toBeInTheDocument()
  })

  it('says so when the period gave nothing for the interests', async () => {
    renderWithProviders(<DigestView digest={makeDigest({ topics: [] })} />)
    expect(
      await screen.findByText('За этот период по выбранным интересам ничего не нашлось.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})

describe('DigestView entries', () => {
  it('sends a reaction with the entry’s place in the whole issue and shows it pressed', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post(apiUrl('/feedback'), async ({ request }) => {
        bodies.push(await request.json())
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = renderWithProviders(
      <DigestView digest={makeDigest({ id: 'digest-7', topics: [vulnerabilities, attacks] })} />,
    )
    const like = await screen.findByRole('button', {
      name: 'Больше такого: Атака на подстанцию',
    })
    await waitFor(() => expect(like).toBeEnabled())
    // A digest keeps every entry: there is nothing to hide.
    expect(screen.queryByRole('button', { name: /^Скрыть:/ })).toBeNull()

    await user.click(like)

    await waitFor(() => expect(like).toHaveAttribute('aria-pressed', 'true'))
    expect(bodies).toEqual([
      {
        article_id: attacks.items[0].article_id,
        kind: 'like',
        active: true,
        context: 'digest',
        // Three entries of «Уязвимости» come first.
        list_id: 'digest-7',
        position: 4,
        slot: 'digest',
      },
    ])
  })

  it('lists the candidates left out, with their score and reason, on request', async () => {
    const { user } = renderWithProviders(
      <DigestView
        digest={makeDigest({
          rejected: [
            makeItem({
              title: 'Обзор рынка SIEM',
              score: 0.42,
              reject_reason: 'low_score',
              reason: 'далеко от интересов',
            }),
            makeItem({ title: 'Реклама вебинара', score: 0.9, reject_reason: 'excluded' }),
          ],
        })}
      />,
    )
    const toggle = await screen.findByRole('button', { name: /Не вошло в выпуск/ })
    expect(toggle).toHaveAccessibleName(/2 кандидата с оценкой и причиной/)
    expect(screen.queryByRole('link', { name: 'Обзор рынка SIEM' })).toBeNull()

    await user.click(toggle)

    const left = (await screen.findByRole('link', { name: 'Обзор рынка SIEM' })).closest('li')!
    expect(left).toHaveTextContent('0.42')
    expect(left).toHaveTextContent('далеко от интересов')
    expect(within(left).getByText('ниже порога')).toBeInTheDocument()
    const excluded = screen.getByRole('link', { name: 'Реклама вебинара' }).closest('li')!
    expect(within(excluded).getByText('исключение')).toBeInTheDocument()
  })
})
