import { render, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Digest } from '../../lib/api'
import { useDigest } from '../../lib/queries'
import {
  makeDigest,
  makeManualWork,
  makePlanEntry,
  makeTagCount,
  makeVulnerabilityChange,
} from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { IssueExtras, ManualWork } from './IssueExtras'

const SIMATIC = 'Сделано: Уязвимость SIMATIC S7-1500 используется в атаках'
const PHISHING = 'Сделано: Фишинг от имени Минэнерго'

const twoLinePlan = () =>
  makeDigest({
    plan: [
      makePlanEntry(),
      makePlanEntry({
        headline: 'Фишинг от имени Минэнерго',
        url: 'https://ics-cert.kaspersky.ru/publications/minenergo-phishing-2026/',
        steps: [],
        facts: [],
      }),
    ],
  })

/**
 * The issue as the server keeps it: a tick sent to it comes back with the
 * next load. Returns the ticks the page sent, in order.
 */
function serveIssue(digest: Digest, { refuse = false } = {}) {
  const ticked = new Set<string>()
  const sent: unknown[] = []
  server.use(
    http.get(apiUrl(`/digests/${digest.id}`), () =>
      HttpResponse.json({
        ...digest,
        plan: digest.plan?.map((entry) => ({ ...entry, done: ticked.has(entry.url) })),
      }),
    ),
    http.put(apiUrl(`/digests/${digest.id}/plan`), async ({ request }) => {
      const tick = (await request.json()) as { url: string; done: boolean }
      sent.push(tick)
      if (refuse)
        return HttpResponse.json({ detail: 'Пункта нет в плане выпуска.' }, { status: 404 })
      if (tick.done) ticked.add(tick.url)
      else ticked.delete(tick.url)
      return HttpResponse.json({ done: [...ticked] })
    }),
  )
  return sent
}

/** The issue as its page shows it: loaded from the server, then kept in the cache. */
function Issue({ id }: { id: string }) {
  const digest = useDigest(id)
  return digest.data ? <IssueExtras digest={digest.data} /> : null
}

describe('ManualWork', () => {
  it('shows nothing when the issue does not count the handwork', () => {
    const { container } = render(<ManualWork digest={makeDigest({ manual: null })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says how long the issue would take by hand and how long the build took', () => {
    const { rerender } = render(
      <ManualWork digest={makeDigest({ manual: makeManualWork({ minutes: 61, seconds: 48 }) })} />,
    )
    expect(screen.getByText('Вместо ручной работы: около 61 мин')).toBeInTheDocument()
    expect(screen.getByText(/ассистенту хватило 48 с/)).toBeInTheDocument()

    rerender(
      <ManualWork digest={makeDigest({ manual: makeManualWork({ minutes: 150, seconds: 0 }) })} />,
    )
    expect(screen.getByText('Вместо ручной работы: около 2,5 ч')).toBeInTheDocument()
    expect(screen.queryByText(/ассистенту хватило/)).toBeNull()
  })

  it('states the pace it counts by, as the server sends it for the audience', () => {
    render(
      <ManualWork
        digest={makeDigest({
          manual: makeManualWork({
            headlines: 1737,
            entries: 15,
            seconds_per_headline: 1.3,
            minutes_per_entry: 7.2,
          }),
        })}
      />,
    )
    expect(
      screen.getByText(/публикаций по 1,3 с и 15 записей по 7,2 мин, по журналу аналитика ИБ/),
    ).toBeInTheDocument()
  })
})

describe('IssueExtras', () => {
  it('shows nothing for an issue without a plan, changes or numbers', () => {
    const { container } = render(<IssueExtras digest={makeDigest()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists the shift’s plan with steps and facts, and ticks a line off', async () => {
    const digest = twoLinePlan()
    serveIssue(digest)
    const { user } = renderWithProviders(<Issue id={digest.id} />)
    expect(await screen.findByRole('heading', { name: 'План на смену' })).toBeInTheDocument()
    expect(
      screen.getByText(/Отмечайте сделанное, отметки сохранятся в этом выпуске/),
    ).toBeInTheDocument()
    const first = screen.getByRole('link', {
      name: 'Уязвимость SIMATIC S7-1500 используется в атаках',
    })
    expect(first).toHaveAttribute('href', 'https://www.securitylab.ru/news/562811.php')
    const row = first.closest('li')!
    expect(within(row).getByText('Обновление: прошивка V3.1.5')).toBeInTheDocument()
    expect(
      within(row).getByText('в каталоге CISA KEV с 10.10.2026, устранить до 31.10.2026'),
    ).toBeInTheDocument()
    expect(within(row).getByText('EPSS 62%')).toBeInTheDocument()

    const done = screen.getByRole('checkbox', { name: SIMATIC })
    await user.click(done)
    expect(done).toBeChecked()
    expect(screen.getByRole('checkbox', { name: PHISHING })).not.toBeChecked()
  })

  it('keeps a ticked line with the issue: folded, unfolded and loaded again', async () => {
    const digest = twoLinePlan()
    const sent = serveIssue(digest)
    const page = renderWithProviders(<Issue id={digest.id} />)

    await page.user.click(await screen.findByRole('checkbox', { name: SIMATIC }))
    expect(screen.getByRole('checkbox', { name: SIMATIC })).toBeChecked()
    await waitFor(() =>
      expect(sent).toEqual([{ url: 'https://www.securitylab.ru/news/562811.php', done: true }]),
    )

    // Folding the block takes its lines off the page; unfolded, the tick is there.
    await page.user.click(screen.getByRole('button', { name: 'Свернуть: план на смену' }))
    await page.user.click(screen.getByRole('button', { name: 'Развернуть: план на смену' }))
    expect(screen.getByRole('checkbox', { name: SIMATIC })).toBeChecked()
    page.unmount()

    // A reload: a fresh page asks the server for the issue again.
    renderWithProviders(<Issue id={digest.id} />)
    expect(await screen.findByRole('checkbox', { name: SIMATIC })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: PHISHING })).not.toBeChecked()
  })

  it('takes a tick back and says so when the server does not keep it', async () => {
    const digest = twoLinePlan()
    serveIssue(digest, { refuse: true })
    const { user } = renderWithProviders(<Issue id={digest.id} />)

    await user.click(await screen.findByRole('checkbox', { name: SIMATIC }))

    expect(await screen.findByText('Отметка не сохранилась')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: SIMATIC })).not.toBeChecked()
  })

  it('tells what became known about vulnerabilities of earlier issues', () => {
    render(<IssueExtras digest={makeDigest({ changes: [makeVulnerabilityChange()] })} />)
    expect(
      screen.getByRole('heading', { name: 'Что изменилось с прошлых выпусков' }),
    ).toBeInTheDocument()
    expect(screen.getByText('CVE-2026-28977')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Обход аутентификации в VPN-шлюзах удалённого доступа' }),
    ).toHaveAttribute('href', 'https://www.securitylab.ru/news/561904.php')
    expect(
      screen.getByText(
        'попала в каталог CISA KEV 13.10.2026; эксплойт: было «нет данных», стало «используется в атаках». В выпуске от 9 окт. этого не было.',
      ),
    ).toBeInTheDocument()
  })

  it('counts management’s period by tag against the previous issue', () => {
    render(
      <IssueExtras
        digest={makeDigest({
          numbers_title: 'Неделя в цифрах',
          numbers: [
            makeTagCount({ tag: 'energy', label: 'Энергетика', count: 4, before: 2 }),
            makeTagCount({ tag: 'law', label: 'Регуляторы', count: 1, before: 3 }),
            makeTagCount({ tag: 'ics', label: 'АСУ ТП', count: 2, before: 2 }),
            makeTagCount({ tag: 'new', label: 'Импортозамещение', count: 5, before: null }),
          ],
        })}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Неделя в цифрах' })).toBeInTheDocument()
    const row = (label: string) => screen.getByText(label).closest('li')!
    expect(row('Энергетика')).toHaveTextContent('+2 к прошлому4')
    expect(row('Регуляторы')).toHaveTextContent('-2 к прошлому1')
    expect(row('АСУ ТП')).toHaveTextContent('как в прошлом выпуске2')
    // The first issue under a tag has nothing to compare with.
    expect(row('Импортозамещение')).toHaveTextContent(/^Импортозамещение5$/)
  })

  it('folds a block away under its head and keeps the fold for the next visit', async () => {
    const digest = makeDigest({ plan: [makePlanEntry()] })
    const { unmount, user } = renderWithProviders(<IssueExtras digest={digest} />)

    await user.click(screen.getByRole('button', { name: 'Свернуть: план на смену' }))
    expect(screen.queryByRole('checkbox')).toBeNull()
    unmount()

    renderWithProviders(<IssueExtras digest={digest} />)
    expect(screen.getByRole('button', { name: 'Развернуть: план на смену' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})
