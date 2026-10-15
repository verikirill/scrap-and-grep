// The charts are drawn for the eye (aria-hidden SVG) and told to a screen
// reader as a table; the tests read the table and the visible labels.
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DayBars, RateBar, RateLines } from './charts'

const DAYS = ['2026-10-11', '2026-10-12', '2026-10-13']

/** The rows of a chart's table: a day and its values, as a screen reader hears them. */
function rows(caption: string) {
  const table = screen.getByRole('table', { name: caption })
  return within(table)
    .getAllByRole('row')
    .map((row) => Array.from(row.querySelectorAll('th, td'), (cell) => cell.textContent))
}

describe('DayBars', () => {
  it('names the peak and lists every day for a screen reader', () => {
    render(<DayBars days={DAYS} values={[380, 1410, 0]} label="Показы статей по дням" />)

    expect(screen.getByText('до 1 410')).toBeInTheDocument()
    expect(rows('Показы статей по дням')).toEqual([
      ['11 окт.', '380'],
      ['12 окт.', '1\u00a0410'],
      ['13 окт.', '0'],
    ])
    // The axis: the first day, the middle one and the last.
    expect(screen.getAllByText('12 окт.')).toHaveLength(2)
  })

  it('says the period had no views instead of drawing an empty scale', () => {
    render(<DayBars days={DAYS} values={[0, 0, 0]} label="Показы" />)

    expect(screen.getByText('За период показов не было')).toBeInTheDocument()
    expect(screen.queryByText(/^до /)).toBeNull()
    expect(rows('Показы')).toEqual([
      ['11 окт.', '0'],
      ['12 окт.', '0'],
      ['13 окт.', '0'],
    ])
  })
})

describe('RateLines', () => {
  it('leaves a day with too little seen as a gap, not a zero', () => {
    render(
      <RateLines
        days={DAYS}
        label="Доля открытий"
        series={[
          { label: 'открывают', tone: 'text-accent', values: [0.12, null, 0.15] },
          { label: 'сохранили', tone: 'text-warning', values: [0.04, 0.05, null] },
        ]}
      />,
    )

    expect(rows('Доля открытий')).toEqual([
      ['День', 'открывают', 'сохранили'],
      ['11 окт.', '12\u00a0%', '4\u00a0%'],
      ['12 окт.', 'мало данных', '5\u00a0%'],
      ['13 окт.', '15\u00a0%', 'мало данных'],
    ])
  })

  it('names each line with its last known rate and scales above the highest one', () => {
    render(
      <RateLines
        days={DAYS}
        label="Доля открытий"
        series={[
          { label: 'открывают', tone: 'text-accent', values: [0.12, null, 0.2] },
          { label: 'сохранили', tone: 'text-warning', values: [0.04, 0.05, null] },
          { label: 'скрыли', tone: 'text-danger', values: [null, null, null] },
        ]}
      />,
    )

    const legend = screen.getByRole('list')
    expect(
      within(legend)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['открывают20\u00a0%', 'сохранили5\u00a0%', 'скрыли'])
    // 15 % above the top value, so the line does not touch the edge.
    // getByText compares with the text's spaces collapsed: a no-break space reads as one.
    expect(screen.getByText('до 23 %')).toBeInTheDocument()
  })

  it('says there are too few views when no day has a rate, and shows its note', () => {
    render(
      <RateLines
        days={DAYS}
        label="Доля открытий"
        note="Дни, где меньше 30 показов, пропущены."
        series={[{ label: 'открывают', tone: 'text-accent', values: [null, null, null] }]}
      />,
    )

    expect(screen.getByText('Мало показов, чтобы считать долю по дням')).toBeInTheDocument()
    expect(screen.queryByText(/^до /)).toBeNull()
    expect(screen.getByText('Дни, где меньше 30 показов, пропущены.')).toBeInTheDocument()
  })
})

describe('RateBar', () => {
  it('tells the interval of a rate on hover', () => {
    render(<RateBar rate={0.15} low={0.13} high={0.17} scale={0.2} />)

    // getByTitle reads a no-break space as a space.
    expect(screen.getByTitle('от 13 % до 17 %')).toBeInTheDocument()
  })

  it('draws no interval for a rate without one', () => {
    render(<RateBar rate={0.15} scale={1} tone="danger" />)

    expect(screen.queryByTitle(/^от /)).toBeNull()
  })
})
