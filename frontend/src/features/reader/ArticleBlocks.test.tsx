import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { API_BASE } from '../../lib/api'
import {
  makeCodeBlock,
  makeHeadingBlock,
  makeImageBlock,
  makeListBlock,
  makeParagraphBlock,
  makeQuoteBlock,
  makeSpan,
  makeTableBlock,
} from '../../test/fixtures'
import type { Block } from '../../lib/api'
import { ArticleBlocks } from './ArticleBlocks'

const renderBlocks = (blocks: Block[]) => render(<ArticleBlocks articleId={7} blocks={blocks} />)

/** The picture as the browser would report it once loaded. */
function load(picture: HTMLElement, width: number, height: number) {
  Object.defineProperty(picture, 'naturalWidth', { value: width })
  Object.defineProperty(picture, 'naturalHeight', { value: height })
  fireEvent.load(picture)
}

describe('ArticleBlocks', () => {
  it('links only to web pages, as nofollow in a new tab', () => {
    renderBlocks([
      makeParagraphBlock({
        spans: [
          makeSpan({ text: 'бюллетень', href: 'https://cert-portal.siemens.com/ssa-482956.html' }),
          makeSpan({ text: ' и ' }),
          makeSpan({ text: 'скрипт', href: 'javascript:alert(1)' }),
          makeSpan({ text: ' и ' }),
          makeSpan({ text: 'файл', href: 'file:///etc/passwd' }),
        ],
      }),
    ])

    expect(screen.getAllByRole('link')).toHaveLength(1)
    const link = screen.getByRole('link', { name: 'бюллетень' })
    expect(link).toHaveAttribute('href', 'https://cert-portal.siemens.com/ssa-482956.html')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer nofollow')
    // The words of a refused link stay in the sentence.
    expect(screen.getByRole('paragraph')).toHaveTextContent('бюллетень и скрипт и файл')
  })

  it('keeps bold, italic and inline code, and quotes as quotes', () => {
    renderBlocks([
      makeParagraphBlock({
        spans: [
          makeSpan({ text: 'CVE-2026-1234', b: true, i: true }),
          makeSpan({ text: ' в ' }),
          makeSpan({ text: 'httpd', code: true }),
        ],
      }),
      makeQuoteBlock(),
    ])

    expect(within(screen.getByRole('strong')).getByRole('emphasis')).toHaveTextContent(
      'CVE-2026-1234',
    )
    expect(screen.getByRole('code')).toHaveTextContent('httpd')
    expect(screen.getByRole('blockquote')).toHaveTextContent(
      'До установки обновления ограничьте доступ к веб-серверу контроллера.',
    )
  })

  it('draws headings at their level, and lists bulleted or numbered', () => {
    renderBlocks([
      makeHeadingBlock({ level: 2, text: 'Кого затрагивает' }),
      makeHeadingBlock({ level: 4, text: 'Модули' }),
      makeListBlock(),
      makeListBlock({ ordered: true, items: [[makeSpan({ text: 'Обновить прошивку' })]] }),
    ])

    expect(screen.getByRole('heading', { level: 2, name: 'Кого затрагивает' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 4, name: 'Модули' })).toBeInTheDocument()
    const [bullets, numbers] = screen.getAllByRole('list')
    expect(bullets.tagName).toBe('UL')
    expect(within(bullets).getAllByRole('listitem')).toHaveLength(2)
    expect(numbers.tagName).toBe('OL')
    expect(within(numbers).getByRole('listitem')).toHaveTextContent('Обновить прошивку')
  })

  it('keeps code as typed, in a block the keyboard can scroll', () => {
    const { container } = renderBlocks([makeCodeBlock({ text: 'if a:\n    run()' })])

    const code = container.querySelector('pre') as HTMLElement
    expect(code.textContent).toBe('if a:\n    run()')
    expect(code).toHaveAttribute('tabindex', '0')
  })

  it('draws a table with its header, in a region the keyboard can scroll', () => {
    renderBlocks([makeTableBlock()])

    const region = screen.getByRole('region', { name: 'Таблица' })
    expect(region).toHaveAttribute('tabindex', '0')
    expect(
      within(region)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Модуль', 'Уязвимые версии', 'Исправление'])
    expect(within(region).getAllByRole('row')).toHaveLength(3)
    expect(within(region).getByRole('cell', { name: 'CPU 1518-4 PN/DP' })).toBeInTheDocument()
  })

  it('draws a table without a header as rows only', () => {
    renderBlocks([makeTableBlock({ head: null })])

    expect(screen.queryAllByRole('columnheader')).toEqual([])
    expect(screen.getAllByRole('row')).toHaveLength(2)
  })

  it('loads pictures through the API and captions those with a description', () => {
    renderBlocks([
      makeImageBlock({ id: 'img 1', alt: 'Контроллеры SIMATIC S7-1500 в шкафу управления' }),
      makeImageBlock({ id: 'img-2', alt: 'Fortinet' }),
    ])

    // A described picture: the caption says it, the picture itself stays silent.
    const caption = screen.getByText('Контроллеры SIMATIC S7-1500 в шкафу управления')
    expect(caption.tagName).toBe('FIGCAPTION')
    const [described] = screen.getAllByRole('presentation')
    expect(described).toHaveAttribute('src', `${API_BASE}/articles/7/images/img%201`)
    expect(described).toHaveAttribute('loading', 'eager')
    // Two words are a name, not a description: they stay the picture's text.
    expect(screen.getByRole('img', { name: 'Fortinet' })).toHaveAttribute('loading', 'lazy')
    expect(screen.getAllByRole('figure')[1].querySelector('figcaption')).toBeNull()
  })

  it('leaves out a picture the site would not give, and an icon-sized one', () => {
    renderBlocks([
      makeImageBlock({ id: 'broken', alt: 'Сломанная' }),
      makeImageBlock({ id: 'icon', alt: 'Иконка' }),
      makeImageBlock({ id: 'thin', alt: 'Полоса' }),
    ])

    fireEvent.error(screen.getByRole('img', { name: 'Сломанная' }))
    load(screen.getByRole('img', { name: 'Иконка' }), 32, 32)
    // Narrow but tall: a picture, not an icon.
    load(screen.getByRole('img', { name: 'Полоса' }), 20, 400)

    expect(screen.queryByRole('img', { name: 'Сломанная' })).toBeNull()
    expect(screen.queryByRole('img', { name: 'Иконка' })).toBeNull()
    expect(screen.getByRole('img', { name: 'Полоса' })).toBeInTheDocument()
    expect(screen.getAllByRole('figure')).toHaveLength(1)
  })
})
