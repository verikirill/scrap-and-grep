import type { PostFormat } from './publishing'

const SAFE_LINK = /^(https?:|tg:)/i

/** A link that opens a page or Telegram and nothing else: no javascript:, no data:. */
export function safeLink(url: string | null | undefined): string | undefined {
  return url && SAFE_LINK.test(url) ? url : undefined
}

const BLOCKS = new Set(['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'BLOCKQUOTE', 'PRE'])

/** A node's words and line breaks: what is left of it once the tags are gone. */
function textOf(node: Node): string {
  if (node.nodeName === 'BR') return '\n'
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? ''
  return Array.from(node.childNodes, textOf).join('')
}

function listItems(list: Element): Element[] {
  return Array.from(list.children).filter((item) => item.tagName === 'LI')
}

/**
 * A block of a classic post as the server writes it for Telegram (backend
 * publishing/markup.py, to_classic): list items on lines of their own after
 * "•" or their number, the blocks of a quote on lines of their own, no spaces
 * at the edges.
 */
function classicBlock(block: Element): string {
  if (block.tagName === 'UL' || block.tagName === 'OL') {
    return listItems(block)
      .map((item, index) => {
        const mark = block.tagName === 'OL' ? `${index + 1}.` : '•'
        return `${mark} ${textOf(item).trim()}`
      })
      .join('\n')
  }
  if (block.tagName === 'BLOCKQUOTE') {
    return Array.from(block.childNodes, (child) =>
      child.nodeType === Node.ELEMENT_NODE ? classicBlock(child as Element) : textOf(child),
    )
      .map((part) => part.trim())
      .filter(Boolean)
      .join('\n')
  }
  return textOf(block).trim()
}

/**
 * A block of a rich post as the server counts it (to_rich): blocks follow one
 * another without a separator, and every list item ends with a line break.
 */
function richBlock(block: Element): string {
  if (block.tagName === 'UL' || block.tagName === 'OL') {
    return listItems(block)
      .map((item) => `${textOf(item).trim()}\n`)
      .join('')
  }
  if (block.tagName === 'BLOCKQUOTE') {
    const inner = Array.from(block.children)
      .filter((child) => BLOCKS.has(child.tagName))
      .map(richBlock)
      .join('')
    return inner || textOf(block).trim()
  }
  return textOf(block).trim()
}

/** The characters Telegram will count for this post (text without markup). */
export function visibleLength(html: string, mode: PostFormat): number {
  const parsed = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html')
  // A block without words, such as the paragraph a blank line leaves, is not sent.
  const blocks = Array.from(parsed.body.children).filter((block) => textOf(block).trim())
  if (mode === 'rich') return blocks.map(richBlock).join('').length
  return blocks.map(classicBlock).join('\n\n').length
}
