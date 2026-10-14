import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ChipsInput } from './ChipsInput'

/** The keywords of a profile: what the field reports is what it shows next. */
function Keywords({
  initial = [],
  max,
  onChange,
}: {
  initial?: string[]
  max?: number
  onChange?: (next: string[]) => void
}) {
  const [values, setValues] = useState(initial)
  return (
    <>
      <ChipsInput
        label="Ключевые слова"
        placeholder="SCADA, Modbus"
        values={values}
        max={max}
        onChange={(next) => {
          setValues(next)
          onChange?.(next)
        }}
      />
      <button type="button">Сохранить</button>
    </>
  )
}

const field = () => screen.getByRole('textbox', { name: 'Ключевые слова' })
const chip = (word: string) => screen.queryByRole('button', { name: `Убрать «${word}»` })

describe('ChipsInput', () => {
  it('adds a word on Enter and on a comma, trimmed, and empties the field', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords onChange={onChange} />)
    expect(field()).toHaveAttribute('placeholder', 'SCADA, Modbus')

    await user.type(field(), '  SCADA  {Enter}')
    await user.type(field(), 'Modbus,')

    expect(onChange.mock.calls).toEqual([[['SCADA']], [['SCADA', 'Modbus']]])
    expect(chip('SCADA')).toBeInTheDocument()
    expect(chip('Modbus')).toBeInTheDocument()
    expect(field()).toHaveValue('')
    // The hint is for an empty field only.
    expect(field()).toHaveAttribute('placeholder', '')
  })

  it('splits a pasted list by commas, skipping empty parts and words already there', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords initial={['SCADA']} onChange={onChange} />)

    await user.click(field())
    await user.paste('Modbus, SCADA, , МЭК 61850')
    await user.keyboard('{Enter}')

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(['SCADA', 'Modbus', 'МЭК 61850'])
    expect(screen.getAllByRole('button', { name: /^Убрать/ })).toHaveLength(3)
  })

  it('reports no change for a word it already has or an empty entry', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords initial={['SCADA']} onChange={onChange} />)

    await user.type(field(), 'SCADA{Enter}')
    await user.type(field(), '   {Enter}')

    expect(onChange).not.toHaveBeenCalled()
    expect(field()).toHaveValue('')
  })

  it('stops at its limit', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords initial={['SCADA', 'Modbus']} max={3} onChange={onChange} />)

    await user.click(field())
    await user.paste('МЭК 61850, DNP3')
    await user.keyboard('{Enter}')

    expect(onChange).toHaveBeenLastCalledWith(['SCADA', 'Modbus', 'МЭК 61850'])
    expect(chip('DNP3')).toBeNull()
  })

  it('takes the last word back on Backspace in an empty field, and only a letter otherwise', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords initial={['SCADA', 'Modbus']} onChange={onChange} />)

    await user.type(field(), 'DN{Backspace}')
    expect(field()).toHaveValue('D')
    expect(onChange).not.toHaveBeenCalled()

    await user.keyboard('{Backspace}{Backspace}')
    expect(onChange).toHaveBeenCalledWith(['SCADA'])
    expect(chip('Modbus')).toBeNull()
    expect(chip('SCADA')).toBeInTheDocument()
  })

  it('keeps a word typed before the reader moves on', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords onChange={onChange} />)

    await user.type(field(), 'DNP3')
    await user.tab()

    expect(screen.getByRole('button', { name: 'Сохранить' })).toHaveFocus()
    expect(onChange).toHaveBeenCalledWith(['DNP3'])
    expect(chip('DNP3')).toBeInTheDocument()
  })

  it('removes a word by its cross', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Keywords initial={['SCADA', 'Modbus', 'DNP3']} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'Убрать «Modbus»' }))

    expect(onChange).toHaveBeenCalledWith(['SCADA', 'DNP3'])
    expect(chip('Modbus')).toBeNull()
  })
})
