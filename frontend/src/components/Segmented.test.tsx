import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Segmented } from './Segmented'

const PERIODS = [
  { value: '1', label: 'Сутки' },
  { value: '7', label: 'Неделя' },
  { value: '30', label: 'Месяц' },
] as const

function Period({ onChange }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState<string>('7')
  return (
    <Segmented
      label="Период"
      value={value}
      options={PERIODS}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
    />
  )
}

describe('Segmented', () => {
  it('is a radio group with the chosen option checked', () => {
    render(<Period />)
    const group = screen.getByRole('radiogroup', { name: 'Период' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Неделя' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Сутки' })).not.toBeChecked()
  })

  it('takes one Tab stop, the chosen option', async () => {
    const user = userEvent.setup()
    render(<Period />)
    await user.tab()
    expect(screen.getByRole('radio', { name: 'Неделя' })).toHaveFocus()
    expect(screen.getByRole('radio', { name: 'Сутки' })).toHaveAttribute('tabindex', '-1')
  })

  it('moves the choice and the focus with arrows, Home and End, wrapping around', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Period onChange={onChange} />)
    await user.tab()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Месяц' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Месяц' })).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Сутки' })).toBeChecked()
    await user.keyboard('{End}')
    expect(screen.getByRole('radio', { name: 'Месяц' })).toBeChecked()
    await user.keyboard('{Home}')
    expect(onChange).toHaveBeenLastCalledWith('1')
  })

  it('checks nothing when the value is none of the options, and arrows start from the first', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Segmented label="Период" value="custom" options={PERIODS} onChange={onChange} />)
    for (const radio of screen.getAllByRole('radio')) expect(radio).not.toBeChecked()
    // The first option still takes the Tab stop.
    await user.tab()
    expect(screen.getByRole('radio', { name: 'Сутки' })).toHaveFocus()

    await user.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenLastCalledWith('7')
    await user.keyboard('{ArrowLeft}')
    expect(onChange).toHaveBeenLastCalledWith('30')
  })

  it('carries a short label for a phone beside the full one', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Segmented
        label="Период"
        value="7"
        options={[
          { value: '7', label: 'Неделя' },
          { value: '14', label: '2 недели', short: '2 нед.' },
        ]}
        onChange={onChange}
      />,
    )
    // jsdom has no breakpoints, so both labels are there: a phone shows the
    // short one, a wider screen the full one.
    const option = screen.getByRole('radio', { name: /2 недели/ })
    expect(within(option).getByText('2 нед.')).toBeInTheDocument()
    expect(within(option).getByText('2 недели')).toBeInTheDocument()
    await user.click(option)
    expect(onChange).toHaveBeenCalledWith('14')
  })

  it('keeps a scrolling row of many options one group the keyboard reaches across', async () => {
    const channels = [
      { value: 'all', label: 'Все' },
      { value: 'channel-1', label: 'Радар ИБ' },
      { value: 'channel-2', label: 'АСУ ТП: дайджест' },
      { value: 'channel-3', label: 'SOC на смене' },
      { value: 'channel-4', label: 'Энергетика и КИИ' },
      { value: 'channel-5', label: 'Регуляторы' },
      { value: 'channel-6', label: 'Утечки' },
    ]
    function Channel() {
      const [value, setValue] = useState('all')
      return (
        <Segmented
          label="Канал"
          isScrollable
          value={value}
          options={channels}
          onChange={setValue}
        />
      )
    }
    const user = userEvent.setup()
    render(<Channel />)
    expect(
      within(screen.getByRole('radiogroup', { name: 'Канал' })).getAllByRole('radio'),
    ).toHaveLength(7)

    await user.tab()
    await user.keyboard('{End}')
    // The far option takes the focus with the choice: the focus is what
    // scrolls an option out of sight into view.
    const last = screen.getByRole('radio', { name: 'Утечки' })
    expect(last).toBeChecked()
    expect(last).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Все' })).toHaveFocus()
    expect(screen.getByRole('radio', { name: 'Все' })).toBeChecked()
  })
})
