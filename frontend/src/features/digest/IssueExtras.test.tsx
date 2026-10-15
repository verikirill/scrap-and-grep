import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  makeDigest,
  makeManualWork,
  makePlanEntry,
  makeTagCount,
  makeVulnerabilityChange,
} from '../../test/fixtures'
import { IssueExtras, ManualWork } from './IssueExtras'

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
})

describe('IssueExtras', () => {
  it('shows nothing for an issue without a plan, changes or numbers', () => {
    const { container } = render(<IssueExtras digest={makeDigest()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists the shift’s plan with steps and facts, and ticks a line off', async () => {
    const user = userEvent.setup()
    render(
      <IssueExtras
        digest={makeDigest({
          plan: [
            makePlanEntry(),
            makePlanEntry({
              headline: 'Фишинг от имени Минэнерго',
              url: 'https://ics-cert.kaspersky.ru/publications/minenergo-phishing-2026/',
              steps: [],
              facts: [],
            }),
          ],
        })}
      />,
    )
    expect(screen.getByRole('heading', { name: 'План на смену' })).toBeInTheDocument()
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

    const done = screen.getByRole('checkbox', {
      name: 'Сделано: Уязвимость SIMATIC S7-1500 используется в атаках',
    })
    await user.click(done)
    expect(done).toBeChecked()
    expect(
      screen.getByRole('checkbox', { name: 'Сделано: Фишинг от имени Минэнерго' }),
    ).not.toBeChecked()
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
    const user = userEvent.setup()
    const digest = makeDigest({ plan: [makePlanEntry()] })
    const { unmount } = render(<IssueExtras digest={digest} />)

    await user.click(screen.getByRole('button', { name: 'Свернуть: план на смену' }))
    expect(screen.queryByRole('checkbox')).toBeNull()
    unmount()

    render(<IssueExtras digest={digest} />)
    expect(screen.getByRole('button', { name: 'Развернуть: план на смену' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})
