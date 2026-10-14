import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeMedia, makePostButton, makePostContent } from '../../test/fixtures'
import { TelegramPreview } from './TelegramPreview'

const PICTURE = 'https://cdn.example.org/s7-1500.jpg'
const TEXT = '<p>Siemens выпустила обновление</p>'

/** Whether a node is drawn before another, reading the post from the top. */
function isAbove(first: Node, second: Node): boolean {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
}

describe('TelegramPreview', () => {
  it('shows the channel, the text and the buttons under the post as a subscriber sees them', () => {
    render(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={makePostContent({
          html: TEXT,
          buttons: [
            makePostButton({ text: 'Читать источник' }),
            makePostButton({ text: 'Бюллетень', url: 'https://cert.example.org/b-12' }),
          ],
        })}
      />,
    )

    const post = screen.getByRole('article')
    expect(within(post).getByText('Энергетика и ИБ')).toBeInTheDocument()
    expect(within(post).getByText('Siemens выпустила обновление')).toBeInTheDocument()
    expect(within(post).getByText('1 · пост')).toBeInTheDocument()
    expect(within(post).getByText('Читать источник')).toBeInTheDocument()
    expect(within(post).getByText('Бюллетень')).toBeInTheDocument()
    // A preview: the buttons are drawn, not followed.
    expect(within(post).queryAllByRole('link')).toEqual([])
  })

  it('draws a rich post as a rich message', () => {
    render(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={makePostContent({
          format: 'rich',
          html: '<ul><li>Первый</li><li>Второй</li></ul>',
        })}
      />,
    )

    expect(screen.getByText('1 · rich')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('shows the first picture of the post, without telling its site where the reader came from', () => {
    render(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={makePostContent({
          html: TEXT,
          media: [makeMedia({ url: PICTURE }), makeMedia({ url: 'https://cdn.example.org/2.jpg' })],
          preview_url: 'https://www.securitylab.ru/news/1.php',
        })}
      />,
    )

    const pictures = screen.getAllByRole('presentation')
    expect(pictures).toHaveLength(1)
    expect(pictures[0]).toHaveAttribute('src', PICTURE)
    expect(pictures[0]).toHaveAttribute('referrerpolicy', 'no-referrer')
  })

  it('falls back to the link preview picture, and shows none when there is neither', () => {
    const preview = 'https://www.securitylab.ru/upload/preview.jpg'
    const { rerender } = render(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={makePostContent({ html: TEXT, preview_url: preview })}
      />,
    )
    expect(screen.getByRole('presentation')).toHaveAttribute('src', preview)

    rerender(
      <TelegramPreview channel="Энергетика и ИБ" content={makePostContent({ html: TEXT })} />,
    )

    expect(screen.queryByRole('presentation')).toBeNull()
    expect(screen.getByText('Siemens выпустила обновление')).toBeInTheDocument()
  })

  it('puts the text under the picture, or above it when the post asks so', () => {
    const content = makePostContent({ html: TEXT, media: [makeMedia({ url: PICTURE })] })
    const { rerender } = render(<TelegramPreview channel="Энергетика и ИБ" content={content} />)
    expect(
      isAbove(screen.getByRole('presentation'), screen.getByText('Siemens выпустила обновление')),
    ).toBe(true)

    rerender(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={{ ...content, caption_above_media: true }}
      />,
    )

    expect(
      isAbove(screen.getByText('Siemens выпустила обновление'), screen.getByRole('presentation')),
    ).toBe(true)
    expect(screen.getAllByText('Siemens выпустила обновление')).toHaveLength(1)
  })

  it('says a picture failed to load, and tries a new address afresh', () => {
    const content = makePostContent({ html: TEXT, media: [makeMedia({ url: PICTURE })] })
    const { rerender } = render(<TelegramPreview channel="Энергетика и ИБ" content={content} />)

    fireEvent.error(screen.getByRole('presentation'))

    expect(screen.getByText('Не удалось загрузить изображение')).toBeInTheDocument()
    expect(screen.queryByRole('presentation')).toBeNull()

    const next = 'https://cdn.example.org/fixed.jpg'
    rerender(
      <TelegramPreview
        channel="Энергетика и ИБ"
        content={{ ...content, media: [makeMedia({ url: next })] }}
      />,
    )

    expect(screen.getByRole('presentation')).toHaveAttribute('src', next)
    expect(screen.queryByText('Не удалось загрузить изображение')).toBeNull()
  })
})
