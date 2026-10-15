import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeAnalytics, makeAnalyticsTotals, makeRates } from '../../test/fixtures'
import { Activity, Days, Figures, Funnel, Panel } from './Panels'

/** A figure's tile: its label, value and change, as one line of text. */
// toHaveTextContent and getByText collapse a no-break space into a space; textContent keeps it.
const figure = (label: string) => screen.getByRole('group', { name: label }).textContent

describe('Panel', () => {
  it('is a region named by its title, with the line under it and the remark at its foot', () => {
    render(
      <Panel icon={<svg />} title="Категории" subtitle="Как часто открывают" note="Дни по UTC.">
        <p>тело</p>
      </Panel>,
    )

    const region = screen.getByRole('region', { name: 'Категории' })
    expect(within(region).getByRole('heading', { level: 2 })).toHaveTextContent('Категории')
    expect(region.textContent).toBe('КатегорииКак часто открываюттелоДни по UTC.')
  })

  it('leaves out the line and the remark it was not given', () => {
    render(
      <Panel icon={<svg />} title="По дням" note={null}>
        <p>тело</p>
      </Panel>,
    )

    expect(screen.getByRole('region', { name: 'По дням' }).textContent).toBe('По днямтело')
  })
})

describe('Figures', () => {
  it('shows each figure with its change against the previous period of the same length', () => {
    render(
      <Figures
        totals={makeAnalyticsTotals({ readers: 48, seen: 1200, opened: 180, liked: 40 })}
        previous={makeAnalyticsTotals({ readers: 40, seen: 1000, opened: 120, liked: 40 })}
        days={30}
      />,
    )

    // Counts change in percent, rates in percentage points.
    expect(figure('Читатели')).toBe('Читатели48+20\u00a0%к предыдущим 30 дням')
    expect(figure('Показано статей')).toBe(
      'Показано статей1\u00a0200+20\u00a0%к предыдущим 30 дням',
    )
    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%+3 п. п.к предыдущим 30 дням')
    expect(figure('Реакции «больше» и сохранения')).toBe(
      'Реакции «больше» и сохранения3,3\u00a0%−0,7 п. п.к предыдущим 30 дням',
    )
  })

  it('says "было 0" for a count that grew from nothing, and shows a change that rounds to nothing as level', () => {
    render(
      <Figures
        totals={makeAnalyticsTotals({ readers: 5, seen: 10_000, opened: 1_501 })}
        previous={makeAnalyticsTotals({ readers: 0, seen: 10_000, opened: 1_500 })}
        days={7}
      />,
    )

    expect(figure('Читатели')).toBe('Читатели5было 0к предыдущим 7 дням')
    expect(figure('Показано статей')).toBe('Показано статей10\u00a00000\u00a0%к предыдущим 7 дням')
    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%0 п. п.к предыдущим 7 дням')
  })

  it('shows no change without a previous period, and no rate change when nothing was seen then', () => {
    const { rerender } = render(
      <Figures totals={makeAnalyticsTotals()} previous={null} days={30} />,
    )
    expect(figure('Читатели')).toBe('Читатели48')

    rerender(
      <Figures
        totals={makeAnalyticsTotals()}
        previous={makeAnalyticsTotals({ seen: 0, opened: 0, liked: 0, rejected: 0 })}
        days={30}
      />,
    )

    expect(figure('Доля открытий')).toBe('Доля открытий15\u00a0%')
    expect(figure('Показано статей')).toMatch(/было 0к предыдущим 30 дням$/)
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

describe('Days', () => {
  it('draws the views of each day and leaves out the rates of days with too few views', () => {
    const daily = makeAnalytics().daily
    render(<Days daily={daily} />)

    const views = screen.getByRole('table', { name: 'Показы статей по дням' })
    expect(within(views).getAllByRole('row')).toHaveLength(daily.length)
    const rates = screen.getByRole('table', { name: 'Доля открытий и отметок' })
    const thin = daily.filter((day) => !day.enough).length
    // Two cells a day, both "мало данных" on a thin day.
    expect(within(rates).queryAllByText('мало данных')).toHaveLength(thin * 2)
    expect(screen.getByText('Дни, где меньше 30 показов, пропущены.')).toBeInTheDocument()
  })
})
