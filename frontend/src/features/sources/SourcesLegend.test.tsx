import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { SourcesLegend } from './SourcesLegend'

describe('SourcesLegend', () => {
  it('spells out the dots, chips and numbers of the table and folds away to its title', async () => {
    const { user } = renderWithProviders(<SourcesLegend />)

    for (const meaning of ['опрошен без ошибок', 'последний опрос с ошибкой', 'выключен']) {
      expect(screen.getByText(meaning)).toBeInTheDocument()
    }
    // Two kinds of source share the word «Страница»: it is explained once.
    expect(screen.getAllByText('Страница')).toHaveLength(1)
    expect(screen.getByText('FlareSolverr')).toBeInTheDocument()
    expect(screen.getByText('Запросы к сайту идут через прокси.')).toBeInTheDocument()
    expect(screen.getByText('Публикаций всего и новых за сутки.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Свернуть: обозначения' }))

    expect(screen.queryByText('опрошен без ошибок')).toBeNull()
    expect(screen.getByText('Обозначения')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Развернуть: обозначения' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })
})
