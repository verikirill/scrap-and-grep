import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Comparison, DigestSummary } from '../lib/api'
import {
  makeComparison,
  makeInterestChange,
  makeItem,
  makeScoreChange,
  makeSummary,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { ComparePage } from './ComparePage'

// Newest first, as the server lists them: the latest specialist issue, its
// manager twin of the same build, the previous specialist issue, one building.
const LATEST = makeSummary({ id: 'digest-3', created_at: '2026-10-14T09:00:00Z' })
const TWIN = makeSummary({
  id: 'digest-3m',
  audience: 'management',
  created_at: '2026-10-14T09:00:00Z',
})
const PREVIOUS = makeSummary({ id: 'digest-2', created_at: '2026-10-13T09:00:00Z' })
const BUILDING = makeSummary({ id: 'digest-4', status: 'running', stage: 'select' })

/** A column of the comparison: its card, under the header that carries its title. */
const column = (title: string) =>
  screen.getByRole('heading', { name: title }).parentElement?.parentElement as HTMLElement

function serveCompare(digests: DigestSummary[], comparison: Comparison = makeComparison()) {
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/digests'), () => HttpResponse.json(digests)),
    http.get(apiUrl('/digests/compare'), ({ request }) => {
      asked.push(new URL(request.url).search)
      return HttpResponse.json(comparison)
    }),
  )
  return asked
}

describe('ComparePage', () => {
  it('asks for a second finished issue when there is only one', async () => {
    const asked = serveCompare([BUILDING, LATEST])
    renderWithProviders(<ComparePage />)

    expect(await screen.findByText('Нужно два готовых выпуска')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Собрать выпуск' })).toHaveAttribute('href', '/')
    expect(asked).toEqual([])
  })

  it('compares the latest issue with the previous one for the same audience, not with its twin', async () => {
    const asked = serveCompare([BUILDING, LATEST, TWIN, PREVIOUS])
    renderWithProviders(<ComparePage />)

    expect(await screen.findByRole('heading', { name: 'Появилось' })).toBeInTheDocument()
    expect(asked).toEqual(['?base=digest-2&other=digest-3'])
    // Each field names its issue: the day, the profile and version, the size.
    expect(
      screen.getByRole('button', { name: /Было: 13 окт\., 12:00 · Инженер АСУ ТП v1 · 12 публ\./ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Стало: 14 окт\., 12:00/ })).toBeInTheDocument()
  })

  it('does not offer the issue chosen on the other side', async () => {
    serveCompare([LATEST, PREVIOUS])
    const { user } = renderWithProviders(<ComparePage />)
    await screen.findByRole('heading', { name: 'Появилось' })

    await user.click(screen.getByRole('button', { name: /Было:/ }))
    const list = await screen.findByRole('listbox', { name: /^Было/ })
    const options = within(list).getAllByRole('option')

    expect(options).toHaveLength(2)
    expect(options[0]).toHaveAttribute('aria-disabled', 'true')
    expect(options[1]).not.toHaveAttribute('aria-disabled')
  })

  it('compares the pair picked and keeps it in the address', async () => {
    const older = makeSummary({ id: 'digest-1', created_at: '2026-10-12T09:00:00Z' })
    const asked = serveCompare([LATEST, PREVIOUS, older])
    const { user } = renderWithProviders(<ComparePage />, { route: '/compare' })
    await screen.findByRole('heading', { name: 'Появилось' })

    await user.click(screen.getByRole('button', { name: /Было:/ }))
    const list = await screen.findByRole('listbox', { name: /^Было/ })
    await user.click(within(list).getAllByRole('option')[2])

    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/compare?base=digest-1&other=digest-3',
      ),
    )
    await waitFor(() => expect(asked).toContain('?base=digest-1&other=digest-3'))
  })

  it('does not compare an issue with itself', async () => {
    const asked = serveCompare([LATEST, PREVIOUS])
    renderWithProviders(<ComparePage />, { route: '/compare?base=digest-3&other=digest-3' })

    expect(
      await screen.findByText('Выбран один и тот же выпуск. Выберите два разных.'),
    ).toBeInTheDocument()
    expect(asked).toEqual([])
  })

  it('lists what came, what left and how the scores of the rest moved', async () => {
    serveCompare(
      [LATEST, PREVIOUS],
      makeComparison({
        added: [makeItem({ headline: 'Новая уязвимость в SCADA', url: 'javascript:alert(1)' })],
        removed: [],
        kept: [
          makeScoreChange({ item: makeItem({ headline: 'Выросла' }), delta: 0.07 }),
          makeScoreChange({ item: makeItem({ headline: 'Упала' }), delta: -0.12 }),
          makeScoreChange({ item: makeItem({ headline: 'На месте' }), delta: 0.004 }),
        ],
        interest_changes: [
          makeInterestChange({ title: 'Атаки на энергетику', change: 'added' }),
          makeInterestChange({ id: 'interest-1', title: 'Уязвимости ПЛК', change: 'changed' }),
        ],
        settings_changed: ['min_score', 'brand_new'],
      }),
    )
    renderWithProviders(<ComparePage />)

    await screen.findByRole('heading', { name: 'Появилось' })
    const added = column('Появилось')
    const link = within(added).getByText('Новая уязвимость в SCADA')
    expect(link.closest('a')).not.toHaveAttribute('href')
    expect(column('Ушло')).toHaveTextContent('Пусто')

    expect(screen.getByText('Выросла').closest('li')).toHaveTextContent(/0\.07$/)
    expect(screen.getByText('Упала').closest('li')).toHaveTextContent(/0\.12$/)
    expect(screen.getByText('На месте').closest('li')).toHaveTextContent(/0\.00$/)

    expect(screen.getByText('Атаки на энергетику: добавлен')).toBeInTheDocument()
    expect(screen.getByText('Уязвимости ПЛК: изменён')).toBeInTheDocument()
    expect(screen.getByText('порог релевантности')).toBeInTheDocument()
    expect(screen.getByText('brand_new')).toBeInTheDocument()
  })

  it('shows why the comparison failed', async () => {
    serveCompare([LATEST, PREVIOUS])
    server.use(
      http.get(apiUrl('/digests/compare'), () =>
        HttpResponse.json({ detail: 'Выпуск удалён' }, { status: 404 }),
      ),
    )
    renderWithProviders(<ComparePage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Выпуск удалён')
  })
})
