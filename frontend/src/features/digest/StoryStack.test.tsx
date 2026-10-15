import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeDuplicate } from '../../test/fixtures'
import { StoryStack } from './StoryStack'

describe('StoryStack', () => {
  it('shows nothing for a story told by one outlet', () => {
    const { container } = render(<StoryStack main="SecurityLab" duplicates={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('counts the publications and lists the other outlets’ headlines on request', async () => {
    const user = userEvent.setup()
    render(
      <StoryStack
        main="SecurityLab"
        duplicates={[
          makeDuplicate(),
          makeDuplicate({
            source_name: 'Хабр',
            title: 'Siemens S7-1500: разбор уязвимости',
            url: 'https://habr.com/ru/news/851234/',
          }),
        ]}
      />,
    )
    const toggle = screen.getByRole('button', { name: 'Сюжет из 3 публикаций' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link')).toBeNull()

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const habr = screen.getByRole('link', { name: /Хабр/ })
    expect(habr).toHaveTextContent('Хабр · Siemens S7-1500: разбор уязвимости')
    expect(habr).toHaveAttribute('href', 'https://habr.com/ru/news/851234/')
    expect(habr).toHaveAttribute('target', '_blank')
    expect(habr).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getAllByRole('link')).toHaveLength(2)

    await user.click(toggle)
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('shows five outlets once each and the rest as a number', () => {
    const outlets = ['Хабр', 'CNews', 'Коммерсант', 'BleepingComputer', 'The Record', 'Хабр']
    render(
      <StoryStack
        main="SecurityLab"
        duplicates={outlets.map((source_name, index) =>
          makeDuplicate({ source_name, url: `https://news.example.org/${index}` }),
        )}
      />,
    )
    // Six outlets besides the main one, Хабр twice: six unique, one past the five faces.
    const toggle = screen.getByRole('button', { name: /Сюжет из 7 публикаций/ })
    expect(within(toggle).getByText('+1')).toBeInTheDocument()
  })

  it('does not link a duplicate whose address is not a web page', async () => {
    const user = userEvent.setup()
    render(
      <StoryStack
        main="SecurityLab"
        duplicates={[makeDuplicate({ url: 'javascript:alert(1)', source_name: 'Чужой сайт' })]}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Сюжет из 2 публикаций' }))
    expect(screen.getByText('Чужой сайт').closest('a')).not.toHaveAttribute(
      'href',
      'javascript:alert(1)',
    )
  })
})
