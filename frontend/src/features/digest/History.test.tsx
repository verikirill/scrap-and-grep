import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DigestSummary } from '../../lib/api'
import { makeSummary } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { History } from './History'

const HOUR_MS = 3_600_000
/** A moment some hours before the test runs: the list says how long ago. */
const hoursAgo = (hours: number) => new Date(Date.now() - hours * HOUR_MS).toISOString()

/** The list's row of an issue, found by its title. */
function row(title: string): HTMLElement {
  const rows = screen
    .getAllByRole('listitem')
    .filter((item) => within(item).queryByText(title) !== null)
  expect(rows).toHaveLength(1)
  return rows[0]
}

function renderHistory(digests: DigestSummary[], activeId?: string) {
  const onSelect = vi.fn()
  const onDelete = vi.fn()
  const result = renderWithProviders(
    <History digests={digests} activeId={activeId} onSelect={onSelect} onDelete={onDelete} />,
  )
  return { ...result, onSelect, onDelete }
}

describe('History', () => {
  it('says where issues will appear while there are none', () => {
    renderHistory([])
    expect(screen.getByText('Здесь появятся собранные выпуски.')).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('tells each issue by its title, its state and when it was asked for', () => {
    renderHistory(
      [
        makeSummary({
          id: 'digest-4',
          title: null,
          status: 'running',
          stats: {},
          created_at: hoursAgo(0),
        }),
        makeSummary({
          id: 'digest-3',
          title: 'Выпуск за неделю',
          audience: 'management',
          origin: 'schedule',
          stats: { selected: 1 },
          created_at: hoursAgo(2),
        }),
        makeSummary({ id: 'digest-2', title: 'Выпуск за сутки', created_at: hoursAgo(26) }),
        makeSummary({
          id: 'digest-1',
          title: 'Выпуск, который не собрался',
          status: 'failed',
          created_at: hoursAgo(50),
        }),
      ],
      'digest-3',
    )

    // An issue without a title yet goes by its profile.
    const building = row('Инженер АСУ ТП')
    expect(within(building).getByText('собирается')).toBeInTheDocument()
    expect(within(building).getByText('Инженер АСУ ТП · только что')).toBeInTheDocument()

    const weekly = row('Выпуск за неделю')
    expect(within(weekly).getByText('1 публикация · 12 окт. – 13 окт.')).toBeInTheDocument()
    expect(
      within(weekly).getByText('Инженер АСУ ТП · руководству · 2 часа назад'),
    ).toBeInTheDocument()
    expect(within(weekly).getByRole('img', { name: 'собран по расписанию' })).toBeInTheDocument()

    const daily = row('Выпуск за сутки')
    expect(within(daily).getByText('12 публикаций · 12 окт. – 13 окт.')).toBeInTheDocument()
    expect(within(daily).getByText('Инженер АСУ ТП · вчера')).toBeInTheDocument()
    expect(within(daily).queryByRole('img', { name: 'собран по расписанию' })).toBeNull()

    expect(
      within(row('Выпуск, который не собрался')).getByText('не удалось собрать'),
    ).toBeInTheDocument()
  })

  it('marks the open issue and opens another one the reader picks', async () => {
    const { user, onSelect } = renderHistory(
      [
        makeSummary({ id: 'digest-2', title: 'Выпуск за неделю' }),
        makeSummary({ id: 'digest-1', title: 'Выпуск за сутки' }),
      ],
      'digest-2',
    )
    const open = screen.getByRole('button', { name: /^Выпуск за неделю/ })
    const other = screen.getByRole('button', { name: /^Выпуск за сутки/ })
    expect(open).toHaveAttribute('aria-current', 'true')
    expect(other).toHaveAttribute('aria-current', 'false')

    await user.click(other)
    expect(onSelect).toHaveBeenCalledWith('digest-1')
  })

  it('deletes an issue only once the reader confirms', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { user, onDelete } = renderHistory([
      makeSummary({ id: 'digest-1', title: 'Выпуск за сутки' }),
    ])
    const remove = screen.getByRole('button', { name: 'Удалить выпуск «Выпуск за сутки»' })

    await user.click(remove)
    expect(confirm).toHaveBeenLastCalledWith('Удалить выпуск «Выпуск за сутки»?')
    expect(onDelete).not.toHaveBeenCalled()

    await user.click(remove)
    expect(onDelete).toHaveBeenCalledExactlyOnceWith('digest-1')
  })

  it('offers no deletion of an issue still being built', () => {
    renderHistory([
      makeSummary({ id: 'digest-4', title: 'В очереди', status: 'queued' }),
      makeSummary({ id: 'digest-3', title: 'Собирается', status: 'running' }),
      makeSummary({ id: 'digest-2', title: 'Не собрался', status: 'failed' }),
      makeSummary({ id: 'digest-1', title: 'Готов' }),
    ])
    expect(
      screen
        .getAllByRole('button', { name: /^Удалить выпуск/ })
        .map((button) => button.getAttribute('aria-label')),
    ).toEqual(['Удалить выпуск «Не собрался»', 'Удалить выпуск «Готов»'])
  })
})
