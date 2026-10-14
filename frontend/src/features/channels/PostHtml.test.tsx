import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PostHtml } from './PostHtml'

/** The innermost element showing this whole line, however its words are split into spans. */
function line(text: string) {
  return (_: string, element: Element | null) =>
    element?.textContent === text &&
    Array.from(element.children).every((child) => child.textContent !== text)
}

/** Every attribute on the drawn post: none may be an event handler. */
function handlerAttributes(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('*')).flatMap((element) =>
    element.getAttributeNames().filter((name) => name.toLowerCase().startsWith('on')),
  )
}

describe('PostHtml', () => {
  it('draws bold, italic, underline, strikethrough, code and spoilers as text formatting', () => {
    render(
      <PostHtml
        mode="classic"
        html={
          '<p><b>жирный</b> <i>курсив</i> <u>подчёркнутый</u> <s>зачёркнутый</s> ' +
          '<code>код</code> <tg-spoiler>тайна</tg-spoiler></p>' +
          // The editor writes strong and em where the server writes b and i.
          '<p><strong>тоже жирный</strong> <em>тоже курсив</em></p>'
        }
      />,
    )

    expect(screen.getAllByRole('strong').map((node) => node.textContent)).toEqual([
      'жирный',
      'тоже жирный',
    ])
    expect(screen.getAllByRole('emphasis').map((node) => node.textContent)).toEqual([
      'курсив',
      'тоже курсив',
    ])
    expect(screen.getByRole('code')).toHaveTextContent('код')
    expect(screen.getByText('подчёркнутый').tagName).toBe('U')
    expect(screen.getByText('зачёркнутый').tagName).toBe('S')
    expect(screen.getByText('тайна')).toBeInTheDocument()
  })

  it('opens links to web pages and Telegram in a new tab that cannot reach back', () => {
    render(
      <PostHtml
        mode="classic"
        html={
          '<p><a href="https://www.securitylab.ru/news/1.php">статья</a> и ' +
          '<a href="tg://resolve?domain=energy_infosec">канал</a></p>'
        }
      />,
    )

    for (const [name, href] of [
      ['статья', 'https://www.securitylab.ru/news/1.php'],
      ['канал', 'tg://resolve?domain=energy_infosec'],
    ]) {
      const link = screen.getByRole('link', { name })
      expect(link).toHaveAttribute('href', href)
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    }
  })

  it('keeps the words of a link that could run code or open a page of its own, without the link', () => {
    const unsafe = [
      'javascript:alert(1)',
      'JaVaScRiPt:alert(1)',
      ' javascript:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'vbscript:msgbox(1)',
      '//evil.example/x',
      '',
    ]
    render(
      <PostHtml
        mode="rich"
        html={`<p>${unsafe.map((href, index) => `<a href="${href}">ссылка ${index}</a>`).join(' ')} <a>без адреса</a></p>`}
      />,
    )

    expect(screen.queryAllByRole('link')).toEqual([])
    unsafe.forEach((_, index) => expect(screen.getByText(`ссылка ${index}`)).toBeInTheDocument())
    expect(screen.getByText('без адреса')).toBeInTheDocument()
  })

  it('never puts markup on the page: no scripts, frames, pictures or handlers, escaped text stays text', () => {
    const { container } = render(
      <PostHtml
        mode="classic"
        html={
          '<p onclick="alert(1)">Текст <img src="x" onerror="alert(2)"> <b onmouseover="alert(3)">жирный</b>' +
          '<script>alert(4)</script></p>' +
          '<iframe src="https://evil.example/"></iframe><style>body { display: none }</style>' +
          '<p>Пример: &lt;script&gt;alert(5)&lt;/script&gt;</p>'
        }
      />,
    )

    expect(container.querySelector('script, iframe, img, style, object, embed')).toBeNull()
    expect(handlerAttributes(container)).toEqual([])
    expect(screen.getByRole('strong')).toHaveTextContent('жирный')
    expect(screen.getByText('Пример: <script>alert(5)</script>')).toBeInTheDocument()
  })

  it('draws a classic post the way Telegram shows a regular message: bold headings, bullets and numbers', () => {
    render(
      <PostHtml
        mode="classic"
        html={
          '<h2>Итог недели</h2><ul><li><p>Первый</p></li><li><p>Второй</p></li></ul>' +
          '<ol><li>Обновить</li><li>Проверить</li></ol>'
        }
      />,
    )

    expect(screen.queryByRole('list')).toBeNull()
    expect(screen.queryByRole('heading')).toBeNull()
    expect(screen.getByText('Итог недели')).toBeInTheDocument()
    for (const text of ['• Первый', '• Второй', '1. Обновить', '2. Проверить']) {
      expect(screen.getByText(line(text))).toBeInTheDocument()
    }
  })

  it('keeps the lists of a rich post as lists, without drawn bullets', () => {
    render(
      <PostHtml
        mode="rich"
        html="<h2>Итог</h2><ul><li>Первый</li><li>Второй</li></ul><ol><li>Обновить</li></ol>"
      />,
    )

    const [bullets, numbers] = screen.getAllByRole('list')
    expect(
      within(bullets)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Первый', 'Второй'])
    expect(within(numbers).getByRole('listitem')).toHaveTextContent('Обновить')
    expect(screen.queryByText(/•/)).toBeNull()
  })

  it('keeps the paragraphs of a quote, and a quote of bare text', () => {
    render(
      <PostHtml
        mode="classic"
        html="<blockquote><p>Первый абзац</p><p>Второй абзац</p></blockquote><blockquote>Просто цитата</blockquote>"
      />,
    )

    const [quote, bare] = screen.getAllByRole('blockquote')
    expect(
      within(quote)
        .getAllByRole('paragraph')
        .map((node) => node.textContent),
    ).toEqual(['Первый абзац', 'Второй абзац'])
    expect(bare).toHaveTextContent('Просто цитата')
  })

  it('shows a code block as typed: line breaks and indents kept, its markup not drawn', () => {
    render(<PostHtml mode="classic" html={'<pre><code>if (a &lt; b) {\n  run()\n}</code></pre>'} />)

    expect(screen.getByText(line('if (a < b) {\n  run()\n}'))).toBeInTheDocument()
    // One monospace block: the code tag inside is not drawn as inline code.
    expect(screen.queryByRole('code')).toBeNull()
  })
})
