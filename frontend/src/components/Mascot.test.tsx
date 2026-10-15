import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { Mascot } from './Mascot'
import type { MascotPose } from './Mascot'

const POSES: MascotPose[] = ['searching', 'found', 'empty', 'error', 'waiting']

const picture = (container: HTMLElement) => container.querySelector('svg.mascot') as SVGElement

describe('Mascot', () => {
  it.each(POSES)('draws the «%s» pose as decoration, hidden from screen readers', (pose) => {
    const { container } = render(<Mascot pose={pose} />)
    const svg = picture(container)
    expect(svg).toHaveAttribute('data-pose', pose)
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('is a named picture when it carries a status', () => {
    render(<Mascot pose="error" label="Выпуск не собрался" />)
    const svg = screen.getByRole('img', { name: 'Выпуск не собрался' })
    expect(svg).not.toHaveAttribute('aria-hidden')
  })

  it('holds up the issue it found instead of the magnifier, and the magnifier otherwise', () => {
    // The magnifier glass is the circle of radius 11; the issue is a sheet (rect).
    const { container, rerender } = render(<Mascot pose="found" />)
    expect(container.querySelector('circle[r="11"]')).toBeNull()
    expect(container.querySelector('rect')).not.toBeNull()
    rerender(<Mascot pose="searching" />)
    expect(container.querySelector('circle[r="11"]')).not.toBeNull()
    expect(container.querySelector('rect')).toBeNull()
  })

  it('moves while motion is welcome and stands still in its pose when motion is reduced', () => {
    const { container, rerender } = render(<Mascot pose="searching" size={64} />)
    expect(picture(container)).toHaveAttribute('data-motion', 'live')
    expect(picture(container)).toHaveAttribute('width', '64')

    setMediaQueries({ '(prefers-reduced-motion: reduce)': true })
    rerender(<Mascot pose="searching" size={64} />)
    expect(picture(container)).toHaveAttribute('data-motion', 'still')
    expect(picture(container)).toHaveAttribute('data-pose', 'searching')
  })

  it('puts a soft disc behind the cat on request', () => {
    const { container, rerender } = render(<Mascot pose="empty" />)
    expect(container.querySelector('.fill-accent-soft')).toBeNull()
    rerender(<Mascot pose="empty" hasBackdrop />)
    expect(container.querySelector('.fill-accent-soft')).not.toBeNull()
  })
})
