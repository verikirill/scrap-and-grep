import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Loading,
  MascotLoader,
  PageSkeleton,
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

describe('MascotLoader', () => {
  it('shows the searching cat with what is being done, as a busy status', () => {
    const { container } = render(
      <MascotLoader label="Проверяем вход" hint="Это пара секунд" size={80} />,
    )
    const status = screen.getByRole('status', { name: 'Проверяем вход' })
    expect(status).toHaveAttribute('aria-busy', 'true')
    expect(within(status).getByText('Проверяем вход')).toBeInTheDocument()
    expect(within(status).getByText('Это пара секунд')).toBeInTheDocument()
    const cat = container.querySelector('svg.mascot')
    expect(cat).toHaveAttribute('data-pose', 'searching')
    expect(cat).toHaveAttribute('width', '80')
  })

  it('sits in a line with a smaller cat where an answer is being written', () => {
    const { container } = render(<MascotLoader label="Читаем записи выпуска" isInline />)
    expect(screen.getByRole('status', { name: 'Читаем записи выпуска' })).toBeInTheDocument()
    expect(container.querySelector('svg.mascot')).toHaveAttribute('width', '44')
  })
})
