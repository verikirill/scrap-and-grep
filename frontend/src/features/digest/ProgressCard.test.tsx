import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeProgressEvent, makeSummary } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { ProgressCard } from './ProgressCard'

type StepState = 'done' | 'current' | 'waiting'

/** The six steps as the reader sees them: ticked off, under way or still ahead. */
function steps(): [string, StepState][] {
  return within(screen.getByRole('list'))
    .getAllByRole('listitem')
    .map((item) => {
      // A step still ahead shows its number before its name.
      const name = (item.textContent ?? '').replace(/\d/g, '')
      if (item.getAttribute('aria-current') === 'step') return [name, 'current']
      return [name, within(item).queryByRole('img', { name: 'готово' }) ? 'done' : 'waiting']
    })
}

const bar = () => screen.getByRole('progressbar', { name: 'Готовность выпуска' })

/** The pose of the cat that walks the track: decoration, so found by its mark. */
const cat = () => document.querySelector('svg.mascot')?.getAttribute('data-pose')

describe('ProgressCard', () => {
  it('shows an issue waiting in the queue with no step under way', () => {
    renderWithProviders(
      <ProgressCard
        digest={makeSummary({ status: 'queued', stage: null, progress: 0 })}
        event={null}
      />,
    )
    expect(screen.getByRole('heading', { name: 'В очереди' })).toBeInTheDocument()
    // A sliver of the bar is drawn from the start: an empty bar reads as stuck.
    expect(bar()).toHaveAttribute('aria-valuenow', '2')
    // The cat waits its turn with a clock, hidden from screen readers.
    expect(cat()).toBe('waiting')
    expect(document.querySelector('svg.mascot')).toHaveAttribute('aria-hidden', 'true')
    expect(steps()).toEqual([
      ['Подготовка', 'waiting'],
      ['Поиск', 'waiting'],
      ['Оценка', 'waiting'],
      ['Отбор', 'waiting'],
      ['Выжимки', 'waiting'],
      ['Сборка', 'waiting'],
    ])
  })

  it('shows the stage of the latest event with its count', () => {
    renderWithProviders(
      <ProgressCard
        digest={makeSummary({ status: 'running', stage: 'retrieve', progress: 0.15 })}
        event={makeProgressEvent({ stage: 'grade', progress: 0.4, done: 16, total: 40 })}
      />,
    )
    expect(screen.getByRole('heading', { name: /^Оцениваем релевантность/ })).toBeInTheDocument()
    expect(screen.getByText('16 из 40')).toBeInTheDocument()
    expect(bar()).toHaveAttribute('aria-valuenow', '40')
    expect(cat()).toBe('searching')
    expect(steps()).toEqual([
      ['Подготовка', 'done'],
      ['Поиск', 'done'],
      ['Оценка', 'current'],
      ['Отбор', 'waiting'],
      ['Выжимки', 'waiting'],
      ['Сборка', 'waiting'],
    ])
  })

  it('shows the stage the issue was saved at until the first event arrives', () => {
    renderWithProviders(
      <ProgressCard
        digest={makeSummary({ status: 'running', stage: 'summarize', progress: 0.7 })}
        event={null}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Пишем выжимки' })).toBeInTheDocument()
    expect(screen.queryByText(/ из /)).toBeNull()
    expect(bar()).toHaveAttribute('aria-valuenow', '70')
    expect(steps().map(([, state]) => state)).toEqual([
      'done',
      'done',
      'done',
      'done',
      'current',
      'waiting',
    ])
  })

  it('takes a running event over an issue still saved as queued, and keeps the bar where it got to', () => {
    renderWithProviders(
      <ProgressCard
        digest={makeSummary({ status: 'queued', stage: null, progress: 0.05 })}
        event={makeProgressEvent({ stage: 'prepare', progress: 0.01, done: null, total: null })}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Готовим публикации' })).toBeInTheDocument()
    expect(screen.queryByText(/ из /)).toBeNull()
    // The event lags behind the saved progress: the bar does not move back.
    expect(bar()).toHaveAttribute('aria-valuenow', '5')
    expect(steps()[0]).toEqual(['Подготовка', 'current'])
  })

  it('ticks off every step while the issue is being saved', () => {
    renderWithProviders(
      <ProgressCard
        digest={makeSummary({ status: 'running', stage: 'compose', progress: 0.9 })}
        event={makeProgressEvent({ stage: 'persist', progress: 0.99, done: null, total: null })}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Сохраняем' })).toBeInTheDocument()
    expect(bar()).toHaveAttribute('aria-valuenow', '99')
    // Saving: the cat holds up the issue it found.
    expect(cat()).toBe('found')
    expect(steps().every(([, state]) => state === 'done')).toBe(true)
  })
})
