import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Loading,
  PageSkeleton,
  PulseLoader,
  Skeleton,
  SkeletonChart,
  SkeletonList,
  SkeletonTable,
  SkeletonText,
} from './loading'

describe('Loading', () => {
  it('announces a busy place once, by its label, and keeps the skeletons out of the way', () => {
    const { container } = render(
      <Loading label="Загружаем источники" className="space-y-2">
        <Skeleton className="h-4" />
        <SkeletonText lines={2} />
      </Loading>,
    )
    const region = screen.getByRole('status', { name: 'Загружаем источники' })
    expect(region).toHaveAttribute('aria-busy', 'true')
    expect(region).toHaveTextContent('Загружаем источники')
    // Every shimmering block is decoration: only the label is read.
    const blocks = container.querySelectorAll('.skeleton')
    expect(blocks).toHaveLength(3)
    for (const block of blocks) expect(block.closest('[aria-hidden="true"]')).not.toBeNull()
  })

  it('draws lists, tables and charts in the shape of what comes', () => {
    const { container } = render(
      <Loading label="Считаем">
        <SkeletonList count={2} />
        <SkeletonTable rows={3} />
        <SkeletonChart />
      </Loading>,
    )
    expect(screen.getByRole('status', { name: 'Считаем' })).toBeInTheDocument()
    // Two cards with a round mark each, three table rows with an avatar each.
    expect(container.querySelectorAll('.skeleton.size-10')).toHaveLength(2)
    expect(container.querySelectorAll('.skeleton.size-8')).toHaveLength(3)
  })

  it('outlines a page while its code arrives', () => {
    render(<PageSkeleton />)
    expect(screen.getByRole('status', { name: 'Открываем раздел' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })
})

describe('PulseLoader', () => {
  it('says what is being done as a busy status, with a pulse kept from screen readers', () => {
    const { container } = render(<PulseLoader label="Проверяем вход" hint="Это пара секунд" />)
    const status = screen.getByRole('status', { name: 'Проверяем вход' })
    expect(status).toHaveAttribute('aria-busy', 'true')
    expect(within(status).getByText('Проверяем вход')).toBeInTheDocument()
    expect(within(status).getByText('Это пара секунд')).toBeInTheDocument()
    // The pulse and the dots are only the picture of a wait.
    const decoration = container.querySelectorAll('[aria-hidden="true"]')
    expect(decoration).toHaveLength(2)
    expect(status.firstElementChild).toBe(decoration[0])
  })

  it('stacks in a column, or sits in a line where an answer is being written', () => {
    const { rerender } = render(<PulseLoader label="Читаем записи выпуска" />)
    const status = () => screen.getByRole('status', { name: 'Читаем записи выпуска' })
    expect(status()).toHaveClass('flex-col')
    rerender(<PulseLoader label="Читаем записи выпуска" isInline />)
    expect(status()).not.toHaveClass('flex-col')
    expect(within(status()).getByText('Читаем записи выпуска')).toHaveClass('text-muted')
  })
})
