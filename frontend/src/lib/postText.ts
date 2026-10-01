import type { PostFormat } from './publishing'

const SAFE_LINK = /^(https?:|tg:)/i

/** A link that opens a page or Telegram and nothing else: no javascript:, no data:. */
export function safeLink(url: string | null | undefined): string | undefined {
  return url && SAFE_LINK.test(url) ? url : undefined
}

/** The characters Telegram will count for this post (text without markup). */
export function visibleLength(html: string, mode: PostFormat): number {
  const parsed = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html')
  const blocks = Array.from(parsed.body.children).map((child) => {
    if (mode === 'classic' && ['UL', 'OL'].includes(child.tagName)) {
      return Array.from(child.children)
        .map((item) => `• ${item.textContent ?? ''}`)
        .join('\n')
    }
    return child.textContent ?? ''
  })
  return blocks.join('\n\n').length
}
