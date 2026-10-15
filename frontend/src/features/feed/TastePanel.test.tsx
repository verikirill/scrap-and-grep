import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeTaste, makeTasteFacet } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { TastePanel } from './TastePanel'

/** A group of the panel by its heading: what it lists. */
function group(title: string) {
  const section = screen.getByRole('heading', { name: title }).closest('section')!
  return within(section)
}

describe('TastePanel', () => {
  it('says how many marks the feed learns from and how much it trusts them', () => {
    renderWithProviders(<TastePanel taste={makeTaste()} />)
    expect(
      screen.getByText(
        '18 отметок за последнее время. Влияние давних отметок со временем снижается.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Доверие к отметкам' })).toHaveAttribute(
      'aria-valuenow',
      '62',
    )
  })

  it('lists stated interests, resume skills, learned and avoided topics, and sources', () => {
    renderWithProviders(<TastePanel taste={makeTaste()} />)
    expect(
      group('Выбранные интересы')
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(['Уязвимости АСУ ТП', 'Атаки на энергетику'])
    expect(group('Навыки из резюме').getByText('МЭК 61850')).toBeInTheDocument()
    // What was learned from marks is quoted: it is the reader's own article, not a topic.
    expect(
      group('Учтено по вашим отметкам').getByText(
        '«Фишинг от имени Минэнерго нацелен на подрядчиков сетевых компаний»',
      ),
    ).toBeInTheDocument()
    expect(
      group('Показываем реже').getByText('«Курс биткоина обновил исторический максимум»'),
    ).toBeInTheDocument()
    expect(group('Источники').getByText('SecurityLab.ru').closest('li')).toHaveTextContent('чаще')
  })

  it('says what is missing for a reader with no marks, interests or resume', () => {
    renderWithProviders(
      <TastePanel
        taste={makeTaste({
          positives: 0,
          negatives: 0,
          facets: [],
          sources: [{ source_id: 3, name: 'Хабр', affinity: -0.3 }],
        })}
      />,
    )
    expect(screen.getByText('Отметок пока нет. Лента учитывает уже первую.')).toBeInTheDocument()
    expect(group('Выбранные интересы').getByText('Профиль интересов не задан.')).toBeVisible()
    expect(group('Навыки из резюме').getByText('Резюме не загружено.')).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Учтено по вашим отметкам' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Показываем реже' })).toBeNull()
    expect(group('Источники').getByText('Хабр').closest('li')).toHaveTextContent('реже')
  })

  it('shows eight learned topics and the rest on request', async () => {
    const learned = Array.from({ length: 11 }, (_, index) =>
      makeTasteFacet({ kind: 'learned', label: `Тема ${index + 1}`, weight: 0.5 }),
    )
    const { user } = renderWithProviders(<TastePanel taste={makeTaste({ facets: learned })} />)
    const topics = group('Учтено по вашим отметкам')
    expect(topics.getAllByRole('listitem')).toHaveLength(8)

    await user.click(topics.getByRole('button', { name: 'Показать ещё 3' }))
    expect(topics.getAllByRole('listitem')).toHaveLength(11)
    await user.click(topics.getByRole('button', { name: 'Свернуть' }))
    expect(topics.getAllByRole('listitem')).toHaveLength(8)
  })

  it('leads to the interests and to the account where the resume is', () => {
    renderWithProviders(<TastePanel taste={makeTaste()} />)
    expect(screen.getByRole('link', { name: '«Интересы»' })).toHaveAttribute('href', '/profiles')
    expect(screen.getByRole('link', { name: 'аккаунте' })).toHaveAttribute('href', '/account')
  })
})
