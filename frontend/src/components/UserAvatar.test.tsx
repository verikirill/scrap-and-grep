import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { UserAvatar } from './UserAvatar'

describe('UserAvatar', () => {
  it('shows the reader’s picture', () => {
    const { container } = render(
      <UserAvatar me={{ display_name: 'Анна Смирнова', avatar_url: '/a/1.png' }} size={32} />,
    )
    expect(container.querySelector('img')).toHaveAttribute('src', '/a/1.png')
    expect(screen.queryByText('АС')).toBeNull()
  })

  it('shows initials without a picture', () => {
    render(<UserAvatar me={{ display_name: 'Анна Смирнова', avatar_url: null }} size={32} />)
    expect(screen.getByText('АС')).toBeInTheDocument()
  })

  it('falls back to initials when the picture fails, and tries a new picture again', () => {
    const { container, rerender } = render(
      <UserAvatar me={{ display_name: 'Анна Смирнова', avatar_url: '/a/1.png' }} size={32} />,
    )
    fireEvent.error(container.querySelector('img')!)
    expect(screen.getByText('АС')).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()

    rerender(
      <UserAvatar me={{ display_name: 'Анна Смирнова', avatar_url: '/a/2.png' }} size={32} />,
    )

    expect(container.querySelector('img')).toHaveAttribute('src', '/a/2.png')
  })
})
