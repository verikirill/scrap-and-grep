import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeAnalytics, makeRankerRun, makeRankerRuns, makeRates } from '../../test/fixtures'
import { Adaptation, Categories, Ranker, Slots, Sources } from './tables'

/** A table as a screen reader walks it: each row, its cells' text. */
function tableRows(name: string) {
  const table = screen.getByRole('table', { name })
  return within(table)
    .getAllByRole('row')
    .map((row) =>
      Array.from(
        row.querySelectorAll('[role="columnheader"], [role="rowheader"], [role="cell"]'),
        (cell) => cell.textContent,
      ),
    )
}

describe('RateRows', () => {
  it('lists each place of the feed with its views and rates, and says when a row has too few views', () => {
    render(
      <Slots
        slots={[
          { ...makeRates({ seen: 820, opened: 131, liked: 40 }), slot: 'ranked' },
          { ...makeRates({ seen: 12, opened: 3 }), slot: 'explore' },
          { ...makeRates({ seen: 40, opened: 4, liked: 2 }), slot: 'mystery' },
        ]}
      />,
    )

    expect(tableRows('Места в ленте и выпусках')).toEqual([
      ['Название', 'показы', 'открыли', '«больше»'],
      ['Лента по интересамс учётом интересов читателя', '820', '16\u00a0%', '4,9\u00a0%'],
      ['Что-то новоекаждая 7-я карточка', '12', 'мало данных'],
      // A place the page does not know keeps the server's name.
      ['mystery', '40', '10\u00a0%', '5\u00a0%'],
    ])
  })

  it('tells the interval of a rate with enough views', () => {
    render(<Slots slots={[{ ...makeRates({ seen: 1200, opened: 180 }), slot: 'ranked' }]} />)

    expect(screen.getByTitle(/^от 13,\d % до 17,\d %$/)).toBeInTheDocument()
  })

  it('says so when there is nothing to break down', () => {
    render(<Slots slots={[]} />)

    expect(screen.getByText('Показов пока нет.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).toBeNull()
  })
})

describe('Sources', () => {
  it('lists the sources read most and those rejected most, or says there are none', () => {
    const { rerender } = render(<Sources data={makeAnalytics()} />)
    expect(tableRows('Чаще открывают').map((row) => row[0])).toEqual([
      'Название',
      'SecurityLab.ru',
      'Kaspersky ICS CERT',
    ])
    expect(tableRows('Чаще отклоняют')).toEqual([
      ['Источник', 'отклоняют'],
      ['OpenNET', '8,8\u00a0%'],
    ])

    rerender(<Sources data={makeAnalytics({ sources_best: [], sources_rejected: [] })} />)

    expect(
      screen.getByText('Ни у одного источника пока нет 30 показов статей.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Отклонённых статей пока нет.')).toBeInTheDocument()
  })
})

describe('Categories', () => {
  it('names each category in Russian and keeps an unknown one as the server sent it', () => {
    render(
      <Categories
        categories={[
          { ...makeRates(), category: 'energy' },
          { ...makeRates(), category: 'space' },
        ]}
      />,
    )

    expect(tableRows('Категории').map((row) => row[0])).toEqual(['Название', 'Энергетика', 'space'])
  })
})

describe('Adaptation', () => {
  it('names each group with its readers in the right form', () => {
    render(
      <Adaptation
        cohorts={[
          { ...makeRates(), adaptive: true, readers: 21 },
          { ...makeRates(), adaptive: false, readers: 3 },
        ]}
      />,
    )

    expect(screen.getByText('21 читатель')).toBeInTheDocument()
    expect(screen.getByText('3 читателя')).toBeInTheDocument()
  })
})

describe('Ranker', () => {
  it('says which model serves the readers and how each night went', () => {
    render(
      <Ranker
        data={makeAnalytics({
          ranker: { share: 0.5, active: '20261014-021500', runs: makeRankerRuns(2) },
        })}
      />,
    )

    expect(screen.getByText('Обученная модель')).toBeInTheDocument()
    expect(screen.getByText(/группа обученной модели · 24 читателя/)).toBeInTheDocument()
    expect(
      screen.getByText(
        'Включена модель 20261014-021500: её порядок выдачи получают 50 % читателей.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('включена')).toBeInTheDocument()
    expect(screen.getByText('не включена')).toBeInTheDocument()
    expect(screen.getByText('nDCG@20 0.412 → 0.447')).toBeInTheDocument()
  })

  it('explains the hand weights when no model is on and nothing was trained yet', () => {
    render(
      <Ranker
        data={makeAnalytics({ variants: [], ranker: { share: 0.5, active: null, runs: [] } })}
      />,
    )

    expect(screen.getByText('Выдач пока нет.')).toBeInTheDocument()
    expect(screen.getByText(/Сейчас ранжирование идёт по ручным весам/)).toBeInTheDocument()
    expect(
      screen.getByText('Обучение ещё не запускалось, оно идёт каждую ночь.'),
    ).toBeInTheDocument()
  })

  it('leaves out the quality of a run that has none, and the nights when there is no ranker', () => {
    const { rerender } = render(
      <Ranker
        data={makeAnalytics({
          ranker: {
            share: 0.5,
            active: null,
            runs: [makeRankerRun({ status: 'retired', hand_ndcg: null, model_ndcg: null })],
          },
        })}
      />,
    )

    expect(screen.getByText('снята')).toBeInTheDocument()
    expect(screen.queryByText(/nDCG@20 \d/)).toBeNull()

    rerender(<Ranker data={makeAnalytics({ ranker: null })} />)

    expect(screen.queryByRole('heading', { name: 'Ночные обучения' })).toBeNull()
  })
})
