import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ProfileSpec } from '../../lib/api'
import { makeInterest, makeInterests, makeSpec } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { ProfileForm } from './ProfileForm'

/** The form as the profile editor holds it: every change comes back as the next spec. */
function renderForm(initial: ProfileSpec) {
  const changes: ProfileSpec[] = []
  function Editor() {
    const [spec, setSpec] = useState(initial)
    return (
      <ProfileForm
        spec={spec}
        onChange={(next) => {
          changes.push(next)
          setSpec(next)
        }}
      />
    )
  }
  const result = renderWithProviders(<Editor />)
  /** The spec the form handed back last. */
  const latest = () => changes.at(-1)
  return { ...result, latest }
}

/** The fields of an interest: the region its row controls. */
function fieldsOf(row: HTMLElement) {
  return within(document.getElementById(row.getAttribute('aria-controls') ?? '') as HTMLElement)
}

async function openInterest(user: UserEvent, name: RegExp) {
  const row = screen.getByRole('button', { name })
  await user.click(row)
  expect(row).toHaveAttribute('aria-expanded', 'true')
  return fieldsOf(row)
}

describe('ProfileForm profile', () => {
  it('asks for a name of two characters at least', async () => {
    const { user, latest } = renderForm(makeSpec())
    const name = screen.getByRole('textbox', { name: /^Название профиля/ })
    expect(name).toHaveValue('Инженер АСУ ТП')
    expect(name).toBeValid()

    await user.clear(name)
    await user.type(name, 'И')

    expect(name).toBeInvalid()
    expect(screen.getByText('Дайте профилю название: хотя бы два символа')).toBeInTheDocument()

    await user.type(name, 'Б')

    expect(name).toBeValid()
    expect(screen.queryByText('Дайте профилю название: хотя бы два символа')).toBeNull()
    expect(latest()?.name).toBe('ИБ')
  })

  it('takes the reader’s role and the format of the issue', async () => {
    const { user, latest } = renderForm(makeSpec())
    const role = screen.getByRole('textbox', { name: /^Роль читателя/ })
    await user.clear(role)
    await user.type(role, 'Руководитель службы ИБ')
    const formats = screen.getByRole('radiogroup', { name: 'Формат выпуска' })
    const specialist = within(formats).getByRole('radio', { name: /^Специалисту/ })
    const management = within(formats).getByRole('radio', { name: /^Руководству/ })
    expect(specialist).toBeChecked()
    expect(management).not.toBeChecked()

    await user.click(management)

    expect(management).toBeChecked()
    expect(specialist).not.toBeChecked()
    expect(latest()).toMatchObject({ role: 'Руководитель службы ИБ', audience: 'management' })
  })
})

describe('ProfileForm interests', () => {
  it('shows each interest folded, with its first keywords and its importance', () => {
    const [vulnerabilities, attacks, rules] = makeInterests(3)
    renderForm(
      makeSpec({
        interests: [
          {
            ...vulnerabilities,
            keywords: ['SCADA', 'Siemens', 'Modbus', 'МЭК 61850', 'ПЛК', 'HMI', 'OPC UA'],
            weight: 1.3,
          },
          { ...attacks, keywords: [], weight: 0.6 },
          { ...rules, weight: 1 },
        ],
      }),
    )
    const first = screen.getByRole('button', { name: /^Уязвимости АСУ ТП/ })
    const second = screen.getByRole('button', { name: /^Атаки на энергетику/ })
    const third = screen.getByRole('button', { name: /^Требования регуляторов/ })
    for (const row of [first, second, third]) {
      expect(row).toHaveAttribute('aria-expanded', 'false')
    }
    expect(within(first).getByText('SCADA, Siemens, Modbus, МЭК 61850, ПЛК, HMI')).toBeVisible()
    expect(within(first).getByText('приоритетный')).toBeInTheDocument()
    expect(within(second).getByText('ключевые слова не заданы')).toBeInTheDocument()
    expect(within(second).getByText('второстепенный')).toBeInTheDocument()
    // An interest of ordinary importance carries no chip.
    expect(within(third).queryByText(/второстепенный|обычный|приоритетный/)).toBeNull()
  })

  it('opens one interest at a time to edit its name, description, keywords and importance', async () => {
    const { user, latest } = renderForm(makeSpec({ interests: makeInterests(2) }))
    const fields = await openInterest(user, /^Уязвимости АСУ ТП/)
    const title = fields.getByRole('textbox', { name: /^Название/ })
    await user.clear(title)
    await user.type(title, 'Уязвимости ПЛК')
    const about = fields.getByRole('textbox', { name: /^Что именно интересует/ })
    await user.clear(about)
    await user.type(about, 'Уязвимости контроллеров Siemens и Schneider')
    await user.type(fields.getByRole('textbox', { name: 'Ключевые слова' }), 'Modbus{Enter}')
    await user.click(fields.getByRole('button', { name: 'Убрать «Siemens»' }))
    fireEvent.change(fields.getByRole('slider', { name: /^Важность/ }), {
      target: { value: '1.3' },
    })

    expect(fields.getByText('приоритетный')).toBeInTheDocument()
    expect(latest()?.interests[0]).toEqual({
      id: 'interest-1',
      title: 'Уязвимости ПЛК',
      description: 'Уязвимости контроллеров Siemens и Schneider',
      keywords: ['SCADA', 'Modbus'],
      weight: 1.3,
    })

    await openInterest(user, /^Атаки на энергетику/)

    expect(screen.getByRole('button', { name: /^Уязвимости ПЛК/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('adds an interest open and unnamed, and flags it once left without a name', async () => {
    const { user, latest } = renderForm(makeSpec())

    await user.click(screen.getByRole('button', { name: 'Добавить' }))

    const row = screen.getByRole('button', { name: /^Новый интерес/ })
    expect(row).toHaveAttribute('aria-expanded', 'true')
    const title = fieldsOf(row).getByRole('textbox', { name: /^Название/ })
    // Not red while the reader is about to type the name.
    expect(title).toBeValid()
    await user.type(title, 'Р')
    expect(title).toBeInvalid()
    expect(title).toHaveAccessibleDescription('Назовите интерес: хотя бы два символа')
    await user.clear(title)

    await user.click(row)

    expect(row).toHaveAttribute('aria-expanded', 'false')
    expect(within(row).getByText('Нужно название')).toBeInTheDocument()
    expect(latest()?.interests).toEqual([
      makeInterest(),
      {
        id: expect.stringMatching(/^interest-/),
        title: '',
        description: '',
        keywords: [],
        weight: 1,
      },
    ])
  })

  it('removes an interest, but never the last one', async () => {
    const { user, latest } = renderForm(makeSpec({ interests: makeInterests(2) }))
    const fields = await openInterest(user, /^Атаки на энергетику/)

    await user.click(fields.getByRole('button', { name: 'Удалить' }))

    // The row leaves through AnimatePresence, a frame after the click.
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /^Атаки на энергетику/ })).toBeNull(),
    )
    expect(latest()?.interests.map((interest) => interest.id)).toEqual(['interest-1'])
    const last = await openInterest(user, /^Уязвимости АСУ ТП/)
    expect(last.getByRole('button', { name: 'Удалить' })).toBeDisabled()
  })

  it('takes twenty interests at most', async () => {
    const { user } = renderForm(makeSpec({ interests: makeInterests(19) }))
    const add = screen.getByRole('button', { name: 'Добавить' })
    expect(add).toBeEnabled()

    await user.click(add)

    expect(add).toBeDisabled()
    expect(screen.getAllByRole('button', { name: /^Новый интерес/ })).toHaveLength(1)
  })
})

describe('ProfileForm filters', () => {
  it('adds exclusions and the company’s systems as chips, twenty exclusions at most', async () => {
    const exclusions = Array.from({ length: 18 }, (_, index) => `тема ${index + 1}`)
    const { user, latest } = renderForm(makeSpec({ exclusions, systems: undefined }))

    await user.type(
      screen.getByRole('textbox', { name: 'Исключения' }),
      'вакансии, обзоры гаджетов, реклама{Enter}',
    )
    await user.type(screen.getByRole('textbox', { name: 'Наши системы' }), 'Siemens S7-1500{Enter}')

    expect(screen.getByRole('button', { name: 'Убрать «обзоры гаджетов»' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Убрать «реклама»' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Убрать «Siemens S7-1500»' })).toBeInTheDocument()
    expect(latest()).toMatchObject({
      exclusions: [...exclusions, 'вакансии', 'обзоры гаджетов'],
      systems: ['Siemens S7-1500'],
    })
  })

  it('sets the relevance threshold and the size of the issue, showing their values', () => {
    const { latest } = renderForm(makeSpec())
    expect(screen.getByText('0.50')).toBeInTheDocument()
    expect(screen.getByText('до 20 публикаций')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('slider', { name: /^Порог релевантности/ }), {
      target: { value: '0.65' },
    })
    fireEvent.change(screen.getByRole('slider', { name: /^Размер выпуска/ }), {
      target: { value: '30' },
    })

    expect(screen.getByText('0.65')).toBeInTheDocument()
    expect(screen.getByText('до 30 публикаций')).toBeInTheDocument()
    expect(latest()).toMatchObject({ min_score: 0.65, max_items: 30 })
  })

  it('narrows the sources to the chosen categories and back to all of them', async () => {
    const { user, latest } = renderForm(makeSpec())
    expect(screen.getByText('все категории')).toBeInTheDocument()
    const ics = screen.getByRole('button', { name: 'АСУ ТП' })
    const regulators = screen.getByRole('button', { name: 'Регуляторы' })
    expect(ics).toHaveAttribute('aria-pressed', 'false')

    await user.click(ics)
    await user.click(regulators)

    expect(ics).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('только выбранные')).toBeInTheDocument()
    expect(latest()?.categories).toEqual(['ics', 'regulator'])

    await user.click(ics)
    await user.click(regulators)

    expect(regulators).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('все категории')).toBeInTheDocument()
    expect(latest()?.categories).toEqual([])
  })
})

describe('ProfileForm card fields', () => {
  it('hides a card row of an attack and shows it again, every row shown at first', async () => {
    const { user, latest } = renderForm(makeSpec())
    const head = screen.getByRole('button', { name: /^Поля карточек/ })
    expect(head).toHaveTextContent('все показаны')

    await user.click(head)
    const attacks = within(screen.getByRole('group', { name: 'Атаки' }))
    const group = attacks.getByRole('checkbox', { name: 'Группировка' })
    expect(group).toBeChecked()

    await user.click(group)

    expect(group).not.toBeChecked()
    expect(latest()?.hidden_card_fields).toEqual(['attack.group'])
    expect(head).toHaveTextContent('скрыто 1 поле')
    // The same name in the other group is a row of its own.
    const vulnerabilities = within(screen.getByRole('group', { name: 'Уязвимости' }))
    expect(vulnerabilities.getByRole('checkbox', { name: 'Сверено по базам' })).toBeChecked()

    await user.click(group)

    expect(latest()?.hidden_card_fields).toEqual([])
    expect(head).toHaveTextContent('все показаны')
  })

  it('offers no card rows to a brief for management, which has no cards', () => {
    renderForm(makeSpec({ audience: 'management' }))
    expect(screen.queryByRole('button', { name: /^Поля карточек/ })).toBeNull()
  })
})
