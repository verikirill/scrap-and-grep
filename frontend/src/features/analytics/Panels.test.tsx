import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  makeAnalytics,
  makeAnalyticsTotals,
  makeRankerRun,
  makeRankerRuns,
  makeRates,
} from '../../test/fixtures'
import { Activity, Adaptation, Figures, Funnel, Ranker, Slots, Sources } from './Panels'

/** The card of a figure: its label, value and change, as one line of text. */
// toHaveTextContent and getByText collapse a no-break space into a space; textContent keeps it.
const figure = (label: string) => screen.getByText(label).closest('div')?.textContent

describe('Figures', () => {
  it('shows each figure with its change against the previous period', () => {
    render(
      <Figures
        totals={makeAnalyticsTotals({ readers: 48, seen: 1200, opened: 180, liked: 40 })}
        previous={makeAnalyticsTotals({ readers: 40, seen: 1000, opened: 120, liked: 40 })}
      />,
    )

    // Counts change in percent, rates in percentage points.
    expect(figure('Читатели')).toBe('Читатели48+20\u00a0%')
    expect(figure('Показано статей')).toBe('Показано статей1\u00a0200+20\u00a0%')
    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%+3 п. п.')
    expect(figure('Реакции «больше» и сохранения')).toBe(
      'Реакции «больше» и сохранения3,3\u00a0%−0,7 п. п.',
    )
  })

  it('says "было 0" for a count that grew from nothing, and shows a change that rounds to nothing as level', () => {
    render(
      <Figures
        totals={makeAnalyticsTotals({ readers: 5, seen: 10_000, opened: 1_501 })}
        previous={makeAnalyticsTotals({ readers: 0, seen: 10_000, opened: 1_500 })}
      />,
    )

    expect(figure('Читатели')).toBe('Читатели5было 0')
    expect(figure('Показано статей')).toBe('Показано статей10\u00a00000\u00a0%')
    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%0 п. п.')
  })

  it('shows no change without a previous period, and no rate change when nothing was seen then', () => {
    const { rerender } = render(<Figures totals={makeAnalyticsTotals()} previous={null} />)
    expect(figure('Читатели')).toBe('Читатели48')

    rerender(
      <Figures
        totals={makeAnalyticsTotals()}
        previous={makeAnalyticsTotals({ seen: 0, opened: 0, liked: 0, rejected: 0 })}
      />,
    )

    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%')
    expect(figure('Показано статей')).toMatch(/было 0$/)
  })
})

describe('Activity', () => {
  it('counts the suggestions accepted out of those decided', () => {
    const { rerender } = render(
      <Activity
        totals={makeAnalyticsTotals({ suggestions_accepted: 5, suggestions_dismissed: 3 })}
      />,
    )
    expect(screen.getByText('5 из 8')).toBeInTheDocument()

    rerender(
      <Activity
        totals={makeAnalyticsTotals({ suggestions_accepted: 0, suggestions_dismissed: 0 })}
      />,
    )
    expect(screen.getByText('Предложений подстройки').nextElementSibling).toHaveTextContent(
      /^0 принято$/,
    )
  })
})

describe('Funnel', () => {
  it('shows each step as a count and a share of what was seen', () => {
    render(<Funnel totals={makeRates({ seen: 1200, opened: 180, liked: 40, rejected: 24 })} />)

    const steps = screen.getAllByRole('listitem').map((step) => step.textContent)
    expect(steps).toEqual([
      'Показано1\u00a0200100\u00a0%',
      'Открыто18015\u00a0%',
      '«Больше такого» и сохранения403,3\u00a0%',
      '«Меньше такого» и скрытия242\u00a0%',
    ])
  })
})

/** A row of a breakdown: its name sits in the row's first cell. */
const row = (name: string) => screen.getByText(name).parentElement?.parentElement as HTMLElement

describe('RateRows', () => {
  it('names the places of the feed and says when a row has too few views', () => {
    render(
      <Slots
        slots={[
          { ...makeRates({ seen: 820, opened: 131 }), slot: 'ranked' },
          { ...makeRates({ seen: 12, opened: 3 }), slot: 'explore' },
          { ...makeRates({ seen: 40, opened: 4 }), slot: 'mystery' },
        ]}
      />,
    )

    expect(screen.getByText('Лента по интересам')).toBeInTheDocument()
    expect(screen.getByText('с учётом интересов читателя')).toBeInTheDocument()
    expect(row('Что-то новое')).toHaveTextContent('мало данных')
    expect(row('Лента по интересам')).toHaveTextContent('16 %')
    // A place the page does not know keeps the server's name.
    expect(screen.getByText('mystery')).toBeInTheDocument()
  })

  it('says so when there is nothing to break down', () => {
    render(<Slots slots={[]} />)

    expect(screen.getByText('Показов пока нет.')).toBeInTheDocument()
  })
})

describe('Sources', () => {
  it('lists the sources read most and those rejected most, or says there are none', () => {
    const { rerender } = render(<Sources data={makeAnalytics()} />)
    expect(screen.getByText('SecurityLab.ru')).toBeInTheDocument()
    expect(screen.getByText('OpenNET').closest('li')).toHaveTextContent('8,8 %')

    rerender(<Sources data={makeAnalytics({ sources_best: [], sources_rejected: [] })} />)

    expect(
      screen.getByText('Ни у одного источника пока нет 30 показов статей.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Отклонённых статей пока нет.')).toBeInTheDocument()
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

  it('leaves out the quality of a run that has none', () => {
    render(
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
  })
})
