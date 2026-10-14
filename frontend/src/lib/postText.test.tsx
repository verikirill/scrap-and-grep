// visibleLength reads markup with DOMParser, which only the jsdom project has;
// safeLink's tests stay in postText.test.ts, in Node.
//
// The editor blocks saving a post over Telegram's limit, and the server refuses
// one (backend publishing/markup.py counts the text it sends). The expected
// numbers below are what the server's visible_length gives for the same markup.
import { describe, expect, it } from 'vitest'
import { visibleLength } from './postText'

/** A post as the editor writes it, with a heading, a line break, a blank line, a list and a quote. */
const EDITED =
  '<h2>Итог</h2><p>Первая строка<br>вторая строка</p><p></p>' +
  '<ol><li><p>Обновить</p></li><li><p>Проверить</p></li></ol>' +
  '<blockquote><p>Цитата</p><p>Продолжение</p></blockquote>'

describe('visibleLength', () => {
  it('counts the text without its markup, an escaped character as one', () => {
    const html = '<p><strong>Жирный</strong> текст <tg-spoiler>тайна</tg-spoiler></p>'
    expect(visibleLength(html, 'classic')).toBe('Жирный текст тайна'.length)
    expect(visibleLength(html, 'rich')).toBe('Жирный текст тайна'.length)
    expect(visibleLength('<p>Счёт &lt;b&gt; &amp;</p>', 'classic')).toBe('Счёт <b> &'.length)
  })

  it('counts a code block as its text', () => {
    expect(visibleLength('<pre><code>a = 1</code></pre>', 'classic')).toBe('a = 1'.length)
  })

  it('counts a line break inside a paragraph', () => {
    expect(visibleLength('<p>Строка<br>вторая</p>', 'classic')).toBe('Строка\nвторая'.length)
    expect(visibleLength('<p>Строка<br>вторая</p>', 'rich')).toBe('Строка\nвторая'.length)
  })

  it('skips the empty paragraphs a blank line leaves in the editor: they are not sent', () => {
    expect(visibleLength('<p>Один</p><p></p><p>Два</p>', 'classic')).toBe('Один\n\nДва'.length)
    expect(visibleLength('<p>   </p><p>Текст</p>', 'classic')).toBe('Текст'.length)
    expect(visibleLength('<p>Один</p><p></p><p>Два</p>', 'rich')).toBe('ОдинДва'.length)
  })
})

describe('visibleLength of a classic post', () => {
  it('puts a blank line between blocks', () => {
    expect(visibleLength('<h2>Итог</h2><p>Текст</p>', 'classic')).toBe('Итог\n\nТекст'.length)
  })

  it('counts a bullet and a line break for every item of a list', () => {
    expect(visibleLength('<ul><li><p>Один</p></li><li><p>Два</p></li></ul>', 'classic')).toBe(
      '• Один\n• Два'.length,
    )
  })

  it('counts the number of every item of a numbered list', () => {
    expect(visibleLength('<ol><li><p>Один</p></li><li><p>Два</p></li></ol>', 'classic')).toBe(
      '1. Один\n2. Два'.length,
    )
    const ten = Array.from({ length: 10 }, (_, index) => `<li>${index + 1}</li>`).join('')
    expect(visibleLength(`<ol>${ten}</ol>`, 'classic')).toBe(51)
  })

  it('puts each block of a quote on its own line', () => {
    expect(visibleLength('<blockquote><p>Один</p><p>Два</p></blockquote>', 'classic')).toBe(
      'Один\nДва'.length,
    )
    expect(
      visibleLength('<blockquote><ul><li><p>Один</p></li></ul><p>Два</p></blockquote>', 'classic'),
    ).toBe('• Один\nДва'.length)
  })

  it('drops the spaces at the edges of a block and of a list item', () => {
    expect(visibleLength('<p> пробелы </p><ul><li><p> пункт </p></li></ul>', 'classic')).toBe(
      'пробелы\n\n• пункт'.length,
    )
  })

  it('agrees with the server on a post written in the editor', () => {
    expect(visibleLength(EDITED, 'classic')).toBe(79)
  })
})

describe('visibleLength of a rich post', () => {
  it('puts nothing between blocks: a rich message keeps them as blocks', () => {
    expect(visibleLength('<h2>Итог</h2><p>Текст</p>', 'rich')).toBe('ИтогТекст'.length)
    expect(visibleLength('<blockquote><p>Один</p><p>Два</p></blockquote>', 'rich')).toBe(
      'ОдинДва'.length,
    )
  })

  it('counts a line break after every list item, without bullets or numbers', () => {
    expect(visibleLength('<ul><li><p>Один</p></li><li><p>Два</p></li></ul>', 'rich')).toBe(
      'Один\nДва\n'.length,
    )
    expect(visibleLength('<ol><li><p>Один</p></li><li><p>Два</p></li></ol>', 'rich')).toBe(
      'Один\nДва\n'.length,
    )
  })

  it('agrees with the server on a post written in the editor', () => {
    expect(visibleLength(EDITED, 'rich')).toBe(67)
  })
})
