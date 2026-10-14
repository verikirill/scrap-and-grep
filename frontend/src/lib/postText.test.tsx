// visibleLength reads markup with DOMParser, which only the jsdom project has;
// safeLink's tests stay in postText.test.ts, in Node.
//
// The editor blocks saving a post over Telegram's limit, and the server refuses
// one (backend publishing/markup.py counts the text it sends). The expected
// numbers below are what the server counts for the same markup.
import { describe, expect, it } from 'vitest'
import { visibleLength } from './postText'

describe('visibleLength', () => {
  it('counts the text without its markup, an escaped character as one', () => {
    const html = '<p><strong>Жирный</strong> текст <tg-spoiler>тайна</tg-spoiler></p>'
    expect(visibleLength(html, 'classic')).toBe('Жирный текст тайна'.length)
    expect(visibleLength(html, 'rich')).toBe('Жирный текст тайна'.length)
    expect(visibleLength('<p>Счёт &lt;b&gt; &amp;</p>', 'classic')).toBe('Счёт <b> &'.length)
  })

  it('puts a blank line between the blocks of a classic post', () => {
    expect(visibleLength('<h2>Итог</h2><p>Текст</p>', 'classic')).toBe('Итог\n\nТекст'.length)
  })

  it('counts a bullet and a line break for every item of a classic list', () => {
    expect(visibleLength('<ul><li><p>Один</p></li><li><p>Два</p></li></ul>', 'classic')).toBe(
      '• Один\n• Два'.length,
    )
  })

  it('counts only the words of a rich post’s list: a rich message keeps the list', () => {
    expect(visibleLength('<ul><li><p>Один</p></li><li><p>Два</p></li></ul>', 'rich')).toBe(
      'ОдинДва'.length,
    )
  })

  it('counts a code block as its text', () => {
    expect(visibleLength('<pre><code>a = 1</code></pre>', 'classic')).toBe('a = 1'.length)
  })
})
