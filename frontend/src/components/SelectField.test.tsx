import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { SelectField } from './SelectField'
import type { SelectOption } from './SelectField'

const AUDIENCES: SelectOption[] = [
  { value: '', label: 'Без аудитории' },
  { value: 'profile-1', label: 'Инженер АСУ ТП' },
  { value: 'profile-2', label: 'Руководство', disabled: true },
  { value: 'profile-3', label: 'SOC' },
]

function Audience({
  initial = '',
  onChange,
}: {
  initial?: string
  onChange?: (v: string) => void
}) {
  const [value, setValue] = useState(initial)
  return (
    <SelectField
      label="Аудитория канала"
      value={value}
      options={AUDIENCES}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
    />
  )
}

describe('SelectField', () => {
  it('names the field with its value, for a screen reader and for voice control', () => {
    render(<Audience initial="profile-1" />)
    expect(
      screen.getByRole('button', { name: /Аудитория канала: Инженер АСУ ТП/ }),
    ).toBeInTheDocument()
  })

  it('picks an option from the themed list and reports its value', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Audience onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: /Аудитория канала/ }))
    const list = await screen.findByRole('listbox', { name: /^Аудитория канала/ })
    await user.click(within(list).getByRole('option', { name: 'SOC' }))

    expect(onChange).toHaveBeenCalledWith('profile-3')
    expect(screen.queryByRole('listbox')).toBeNull()
    expect(screen.getByRole('button', { name: /Аудитория канала: SOC/ })).toBeInTheDocument()
  })

  it('gives the "none" option back as an empty value', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Audience initial="profile-3" onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /Аудитория канала/ }))
    await user.click(await screen.findByRole('option', { name: 'Без аудитории' }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('does not pick a disabled option', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Audience onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /Аудитория канала/ }))
    const option = await screen.findByRole('option', { name: 'Руководство' })
    expect(option).toHaveAttribute('aria-disabled', 'true')
    await user.click(option)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('shows its value but cannot be opened while disabled', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <>
        <SelectField
          label="Аудитория канала"
          value="profile-1"
          options={AUDIENCES}
          onChange={onChange}
          disabled
        />
        <SelectField
          label="Тон"
          value="calm"
          options={[
            { value: 'calm', label: 'Спокойный' },
            { value: 'brief', label: 'Кратко' },
          ]}
          onChange={() => {}}
        />
      </>,
    )
    const locked = screen.getByRole('button', { name: /Аудитория канала: Инженер АСУ ТП/ })
    expect(locked).toBeDisabled()
    await user.click(locked)

    // Tab passes the locked field by, and the next one opens: its list is the only one.
    await user.tab()
    expect(screen.getByRole('button', { name: /Тон/ })).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(await screen.findByRole('listbox')).toHaveAccessibleName(/^Тон/)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('is driven by the keyboard: open, move, choose', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Audience initial="profile-1" onChange={onChange} />)
    await user.tab()
    await user.keyboard('{ArrowDown}')
    await screen.findByRole('listbox')
    // From the chosen option, down skips the disabled one.
    await user.keyboard('{ArrowDown}{Enter}')
    expect(onChange).toHaveBeenCalledWith('profile-3')
  })
})
