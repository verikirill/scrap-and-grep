import { act, screen, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Preview, ProfileSpec } from '../../lib/api'
import { usePreview } from '../../lib/queries'
import {
  makeInterest,
  makeInterests,
  makePreview,
  makePreviewItems,
  makeSpec,
} from '../../test/fixtures'
import { renderHookWithProviders, renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { PreviewPanel } from './PreviewPanel'

type PreviewRequest = { profile: ProfileSpec; period_days: number }

/** Answer every preview with `answer`; the requests are kept in order. */
function servePreview(
  answer: (request: PreviewRequest) => Preview | Promise<Preview> = () => makePreview(),
) {
  const asked: PreviewRequest[] = []
  server.use(
    http.post(apiUrl('/selection/preview'), async ({ request }) => {
      const body = (await request.json()) as PreviewRequest
      asked.push(body)
      return HttpResponse.json(await answer(body))
    }),
  )
  return asked
}

const keywordsOf = (request: PreviewRequest) => request.profile.interests[0]?.keywords

describe('PreviewPanel', () => {
  it('shows what the draft selects over a day: counts, scores, sources and interests', async () => {
    const items = makePreviewItems(2)
    const asked = servePreview(() => makePreview({ selected: 12, candidates: 40, items }))
    const spec = makeSpec()
    renderWithProviders(<PreviewPanel draft={spec} saved={spec} isDirty={false} />)

    const rows = await screen.findAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent(`0.82${items[0].title}`)
    expect(within(rows[0]).getByRole('link', { name: items[0].title })).toHaveAttribute(
      'href',
      items[0].url,
    )
    expect(rows[0]).toHaveTextContent(`${items[0].source_name} · Уязвимости АСУ ТП`)
    expect(screen.getByText(/из 40 кандидатов/)).toHaveTextContent('12 из 40 кандидатов')
    expect(screen.getByText('300 публикаций за период')).toBeInTheDocument()
    expect(screen.getByText(/^За сутки по текущим настройкам/)).toBeInTheDocument()
    // An unchanged profile carries no movement marks and no comparison.
    expect(screen.queryByRole('img', { name: /после правки|Оценка/ })).toBeNull()
    expect(screen.queryByText('по сравнению с сохранённым профилем')).toBeNull()
    // The name and the role do not take part in the selection.
    expect(asked[0]).toEqual({
      profile: { ...spec, name: 'preview', role: '' },
      period_days: 1,
    })
  })

  it('looks a week back for an issue for the management', async () => {
    const asked = servePreview()
    const spec = makeSpec({ audience: 'management' })
    renderWithProviders(<PreviewPanel draft={spec} saved={spec} isDirty={false} />)

    expect(await screen.findByText(/^За неделю по текущим настройкам/)).toBeInTheDocument()
    await screen.findAllByRole('listitem')
    expect(asked.map((request) => request.period_days)).toEqual([7])
  })

  it('marks what an edit adds, raises, lowers and drops against the saved profile', async () => {
    const [kept, raised, lowered, dropped, added] = makePreviewItems(5)
    const saved = makeSpec()
    const draft = makeSpec({ interests: [makeInterest({ keywords: ['SCADA', 'Modbus'] })] })
    servePreview((request) =>
      keywordsOf(request)?.includes('Modbus')
        ? makePreview({
            items: [
              kept,
              { ...raised, score: raised.score + 0.1 },
              { ...lowered, score: lowered.score - 0.1 },
              added,
              { ...dropped, selected: false, reject_reason: 'below_threshold' },
            ],
          })
        : makePreview({ items: [kept, raised, lowered, dropped] }),
    )
    renderWithProviders(<PreviewPanel draft={draft} saved={saved} isDirty />)

    expect(await screen.findByText('+1 новая')).toBeInTheDocument()
    expect(screen.getByText('-1 выпала')).toBeInTheDocument()
    expect(screen.getByText('по сравнению с сохранённым профилем')).toBeInTheDocument()
    const row = (title: string) =>
      screen.getAllByRole('listitem').find((item) => item.textContent?.includes(title))
    expect(within(row(added.title) as HTMLElement).getByRole('img')).toHaveAccessibleName(
      'Появилась после правки',
    )
    expect(within(row(raised.title) as HTMLElement).getByRole('img')).toHaveAccessibleName(
      'Оценка выросла',
    )
    expect(within(row(lowered.title) as HTMLElement).getByRole('img')).toHaveAccessibleName(
      'Оценка снизилась',
    )
    expect(within(row(kept.title) as HTMLElement).queryByRole('img')).toBeNull()
    expect(screen.getByText('Выпали после правки')).toBeInTheDocument()
    expect(screen.getByText(dropped.title)).not.toHaveAttribute('href')
  })

  it('asks for a name of every interest instead of asking the server', () => {
    const asked = servePreview()
    const draft = makeSpec({ interests: [makeInterest(), makeInterest({ id: 'x', title: '' })] })
    renderWithProviders(<PreviewPanel draft={draft} saved={null} isDirty />)

    expect(
      screen.getByText('Дайте название каждому интересу, и здесь появится подборка.'),
    ).toBeInTheDocument()
    expect(asked).toEqual([])
  })

  it('advises a lower threshold when nothing passes it', async () => {
    servePreview(() => makePreview({ selected: 0, items: [] }))
    const spec = makeSpec()
    renderWithProviders(<PreviewPanel draft={spec} saved={spec} isDirty={false} />)

    expect(await screen.findByText(/^Ни одна публикация не проходит порог/)).toHaveTextContent(
      'Добавьте ключевые слова или снизьте порог релевантности.',
    )
  })

  it('shows the server’s reason when the preview fails', async () => {
    server.use(
      http.post(apiUrl('/selection/preview'), () =>
        HttpResponse.json({ detail: 'Индекс публикаций перестраивается' }, { status: 503 }),
      ),
    )
    const spec = makeSpec()
    renderWithProviders(<PreviewPanel draft={spec} saved={null} isDirty />)

    expect(await screen.findByText('Индекс публикаций перестраивается')).toBeInTheDocument()
  })

  it('says when only full-text search could pick the publications', async () => {
    servePreview(() => makePreview({ lexical_only: true }))
    const spec = makeSpec()
    renderWithProviders(<PreviewPanel draft={spec} saved={spec} isDirty={false} />)

    expect(
      await screen.findByText(
        'Поиск: без модели (n-граммы) · векторный поиск недоступен, работает только полнотекстовый',
      ),
    ).toBeInTheDocument()
  })
})

describe('usePreview', () => {
  const withKeywords = (keywords: string[]) => makeSpec({ interests: [makeInterest({ keywords })] })

  it('asks for the draft once typing has paused for 450 ms', async () => {
    vi.useFakeTimers()
    const asked = servePreview()
    const { rerender, result } = renderHookWithProviders(
      ({ spec }: { spec: ProfileSpec }) => usePreview(spec, 1),
      { initialProps: { spec: withKeywords(['SCADA']) } },
    )
    await vi.waitFor(() => expect(result.current.data).toBeDefined())

    rerender({ spec: withKeywords(['SCADA', 'Mod']) })
    act(() => vi.advanceTimersByTime(300))
    rerender({ spec: withKeywords(['SCADA', 'Modbus']) })
    act(() => vi.advanceTimersByTime(449))
    // Still the preview of the last pause, and nothing on its way.
    expect(result.current.isFetching).toBe(false)
    act(() => vi.advanceTimersByTime(1))
    expect(result.current.isFetching).toBe(true)

    await vi.waitFor(() => expect(asked).toHaveLength(2))
    expect(asked.map(keywordsOf)).toEqual([['SCADA'], ['SCADA', 'Modbus']])
  })

  it('does not ask again when only the name or the role changed', async () => {
    vi.useFakeTimers()
    const asked = servePreview()
    const spec = withKeywords(['SCADA'])
    const { rerender, result } = renderHookWithProviders(
      ({ spec: current }: { spec: ProfileSpec }) => usePreview(current, 1),
      { initialProps: { spec } },
    )
    await vi.waitFor(() => expect(result.current.data).toBeDefined())

    rerender({ spec: { ...spec, name: 'Руководитель ИБ', role: 'Отвечает за КИИ' } })
    act(() => vi.advanceTimersByTime(1000))
    expect(result.current.isFetching).toBe(false)
    // A real change after it is the sentinel: it is the second request, not the third.
    rerender({ spec: withKeywords(['ПЛК']) })
    vi.advanceTimersByTime(450)

    await vi.waitFor(() => expect(asked).toHaveLength(2))
    expect(asked.map(keywordsOf)).toEqual([['SCADA'], ['ПЛК']])
  })

  it('drops the last preview once the draft has an interest without a name', async () => {
    servePreview()
    const spec = makeSpec({ interests: makeInterests(2) })
    const { rerender, result } = renderHookWithProviders(
      ({ spec: current }: { spec: ProfileSpec }) => usePreview(current, 1, 0),
      { initialProps: { spec } },
    )
    await vi.waitFor(() => expect(result.current.data).toBeDefined())

    rerender({
      spec: { ...spec, interests: [spec.interests[0], { ...spec.interests[1], title: 'А' }] },
    })

    await vi.waitFor(() => expect(result.current.isValid).toBe(false))
    expect(result.current.data).toBeUndefined()
  })
})
