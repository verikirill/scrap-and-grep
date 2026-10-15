import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { SourceHealth as Health } from '../../lib/api'
import { makeFailingSource, makeSilentSource, makeSourceHealth } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { SourceHealth } from './SourceHealth'

const HOUR_MS = 3_600_000

/** A moment some hours before now: the block tells times relative to the clock. */
const hoursAgo = (hours: number) => new Date(Date.now() - hours * HOUR_MS).toISOString()

function serveHealth(health: Health) {
  server.use(http.get(apiUrl('/sources/health'), () => HttpResponse.json(health)))
}

/** The summary line, read whole: its parts sit in spans of their own. */
async function findSummary() {
  return screen.findByText(
    (_, node) =>
      node?.tagName === 'P' && Boolean(node.textContent?.startsWith('Источники за сутки:')),
  )
}

describe('SourceHealth', () => {
  it('sums up a day of polls and says why polls failed, which sources fail and which went quiet', async () => {
    serveHealth(
      makeSourceHealth({
        failing: [makeFailingSource({ since: hoursAgo(13) })],
        silent: [makeSilentSource({ last_article: hoursAgo(50), longest_gap_hours: 26 })],
      }),
    )
    renderWithProviders(<SourceHealth />)

    expect(await findSummary()).toHaveTextContent(
      'Источники за сутки: 9 600 опросов, 98% успешно · не читаются: 1 · давно не публиковали: 1',
    )
    // Each kind of failure in the reader's words, with what it means on hover.
    expect(screen.getByText('сайт не ответил вовремя — 112 раз')).toHaveAttribute(
      'title',
      'Сайт не ответил за отведённое время.',
    )
    expect(screen.getByText('сайт не пускает бота — 54 раза')).toBeInTheDocument()
    expect(screen.getByText('сменилась вёрстка — 22 раза')).toBeInTheDocument()

    // The failing source keeps the error text for a hover over its line.
    expect(screen.getByTitle('ReadTimeout: timed out')).toHaveTextContent(
      'Минэнерго России — сайт не ответил вовремя: 6 опросов подряд с ошибкой, последний удачный 13 часов назад',
    )
    expect(screen.getByText(/^— последняя публикация/)).toHaveTextContent(
      '— последняя публикация позавчера, а за месяц пауза не превышала 26 ч',
    )
    expect(screen.queryByText('Все источники доступны и обновляются вовремя.')).toBeNull()
  })

  it('never rounds a day with failed polls up to a clean hundred percent', async () => {
    serveHealth(makeSourceHealth({ polls: 4245, ok: 4229 }))
    renderWithProviders(<SourceHealth />)
    expect(await findSummary()).toHaveTextContent('4 245 опросов, 99,6% успешно')
  })

  it('says every source is fine when nothing failed and nothing went quiet', async () => {
    serveHealth(makeSourceHealth({ polls: 96, ok: 96, errors: {}, failing: [], silent: [] }))
    renderWithProviders(<SourceHealth />)

    expect(await findSummary()).toHaveTextContent('Источники за сутки: 96 опросов, 100% успешно')
    expect(await findSummary()).not.toHaveTextContent('не читаются')
    expect(screen.getByText('Все источники доступны и обновляются вовремя.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Почему опросы не прошли' })).toBeNull()
  })

  it('says there were no polls yet on a fresh install', async () => {
    serveHealth(makeSourceHealth({ polls: 0, ok: 0, errors: {}, failing: [], silent: [] }))
    renderWithProviders(<SourceHealth />)
    expect(await findSummary()).toHaveTextContent('Источники за сутки: опросов ещё не было')
  })

  it('names a failure of an unknown kind by its code and one of no kind as another error', async () => {
    serveHealth(
      makeSourceHealth({
        errors: { captcha: 3 },
        failing: [
          makeFailingSource({ name: 'OpenNET', kind: null, error: null, since: null, failures: 1 }),
        ],
        silent: [makeSilentSource({ last_article: hoursAgo(3), longest_gap_hours: 0.5 })],
      }),
    )
    renderWithProviders(<SourceHealth />)

    const chip = await screen.findByText('captcha — 3 раза')
    // No hint to give for a kind the app does not know.
    expect(chip).not.toHaveAttribute('title')
    // Without a kind, a known last success or an error text: just the count.
    expect(screen.getByText(/^— другая ошибка/)).toHaveTextContent(
      /^— другая ошибка: 1 опрос подряд с ошибкой$/,
    )
    expect(screen.getByText(/^— последняя публикация/)).toHaveTextContent(
      '— последняя публикация 3 часа назад, а за месяц пауза не превышала часа',
    )
  })

  it('shows five sources of a long list and the rest on request', async () => {
    const names = ['Альфа', 'Бета', 'Гамма', 'Дельта', 'Эпсилон', 'Зета', 'Эта']
    serveHealth(
      makeSourceHealth({
        failing: names.map((name, index) => makeFailingSource({ source_id: index + 1, name })),
        silent: [],
      }),
    )
    const { user } = renderWithProviders(<SourceHealth />)

    expect(await screen.findByText('Эпсилон')).toBeInTheDocument()
    expect(screen.queryByText('Зета')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Показать все 7' }))
    expect(screen.getByText('Эта')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Показать первые 5' }))
    expect(screen.queryByText('Эта')).toBeNull()
    expect(screen.getByRole('button', { name: 'Показать все 7' })).toBeInTheDocument()
  })

  it('folds to its summary and stays folded on the next visit', async () => {
    serveHealth(makeSourceHealth())
    const first = renderWithProviders(<SourceHealth />)

    await first.user.click(
      await screen.findByRole('button', { name: 'Свернуть: состояние источников' }),
    )
    expect(screen.queryByText('Почему опросы не прошли')).toBeNull()
    expect(await findSummary()).toHaveTextContent('не читаются: 1')
    first.unmount()

    renderWithProviders(<SourceHealth />)
    expect(
      await screen.findByRole('button', { name: 'Развернуть: состояние источников' }),
    ).toHaveAttribute('aria-expanded', 'false')
    expect(await findSummary()).toHaveTextContent('Источники за сутки: 9 600 опросов')
    expect(screen.queryByText('Почему опросы не прошли')).toBeNull()
  })
})
