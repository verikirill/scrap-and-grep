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

  it('shows the ready picture of the account while there is no photo, sharp on dense screens', () => {
    const { container } = render(
      <UserAvatar
        me={{ display_name: 'Анна Смирнова', avatar_url: null, avatar_preset: 'purple' }}
        size={32}
      />,
    )
    const image = container.querySelector('img')
    expect(image).toHaveAttribute('src', '/brand/avatars/purple.webp')
    expect(image).toHaveAttribute(
      'srcset',
      '/brand/avatars/purple.webp 1x, /brand/avatars/purple@2x.webp 2x',
    )
    expect(screen.queryByText('АС')).toBeNull()
  })

  it('shows the photo over the ready picture, and the ready picture if the photo fails', () => {
    const { container } = render(
      <UserAvatar
        me={{ display_name: 'Гость', avatar_url: '/a/1.png', avatar_preset: 'red', is_demo: true }}
        size={32}
      />,
    )
    expect(container.querySelector('img')).toHaveAttribute('src', '/a/1.png')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toHaveAttribute('src', '/brand/avatars/red.webp')
  })

  it('shows initials without a picture', () => {
    render(<UserAvatar me={{ display_name: 'Анна Смирнова', avatar_url: null }} size={32} />)
    expect(screen.getByText('АС')).toBeInTheDocument()
  })

  it('gives a guest without a picture the guest character, and a guest’s own picture wins', () => {
    const { container, rerender } = render(
      <UserAvatar me={{ display_name: 'Гость', avatar_url: null, is_demo: true }} size={36} />,
    )
    expect(container.querySelector('img')).toHaveAttribute('src', '/brand/guest.webp')
    expect(screen.queryByText('Г')).toBeNull()

    rerender(
      <UserAvatar
        me={{ display_name: 'Гость', avatar_url: '/a/2.png', is_demo: true }}
        size={36}
      />,
    )
    expect(container.querySelector('img')).toHaveAttribute('src', '/a/2.png')
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
