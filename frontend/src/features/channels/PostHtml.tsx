import type { ReactNode } from 'react'
import { safeLink } from '../../lib/postText'

/*
 * A post's markup drawn as React elements. The backend already rebuilds every
 * post from an allowlist, and this walks the same allowlist again: no HTML
 * reaches the page as HTML, links keep only http(s) and tg addresses.
 * "classic" draws it the way Telegram shows a regular post (headings as bold
 * lines, bullets as "•"), "rich" the way it shows a rich message.
 */

type Mode = 'classic' | 'rich'

function inline(node: Node, key: number): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent
  if (node.nodeType !== Node.ELEMENT_NODE) return null
  const element = node as Element
  const children = Array.from(element.childNodes).map((child, index) => inline(child, index))
  switch (element.tagName.toLowerCase()) {
    case 'b':
    case 'strong':
      return <strong key={key}>{children}</strong>
    case 'i':
    case 'em':
      return <em key={key}>{children}</em>
    case 'u':
      return <u key={key}>{children}</u>
    case 's':
      return <s key={key}>{children}</s>
    case 'code':
      return (
        <code
          key={key}
          className="rounded bg-black/10 px-1 font-mono text-[0.92em] dark:bg-white/10"
        >
          {children}
        </code>
      )
    case 'tg-spoiler':
      return (
        <span key={key} className="rounded bg-current/30 blur-[3px] transition hover:blur-none">
          {children}
        </span>
      )
    case 'br':
      return <br key={key} />
    case 'a': {
      const href = element.getAttribute('href') ?? ''
      if (!safeLink(href)) return <span key={key}>{children}</span>
      return (
        <a
          key={key}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#3390ec] hover:underline dark:text-[#6ab3f3]"
        >
          {children}
        </a>
      )
    }
    default:
      return <span key={key}>{children}</span>
  }
}

function block(element: Element, key: number, mode: Mode): ReactNode {
  const tag = element.tagName.toLowerCase()
  const kids = (el: Element) =>
    Array.from(el.childNodes).map((child, index) => inline(child, index))
  if (tag === 'ul' || tag === 'ol') {
    const items = Array.from(element.children).filter(
      (child) => child.tagName.toLowerCase() === 'li',
    )
    if (mode === 'classic') {
      return (
        <div key={key}>
          {items.map((item, index) => (
            <div key={index}>
              {tag === 'ol' ? `${index + 1}. ` : '• '}
              {kids(item)}
            </div>
          ))}
        </div>
      )
    }
    const List = tag
    return (
      <List key={key} className={tag === 'ol' ? 'list-decimal pl-5' : 'list-disc pl-5'}>
        {items.map((item, index) => (
          <li key={index}>{kids(item)}</li>
        ))}
      </List>
    )
  }
  if (tag === 'h2' || tag === 'h3') {
    if (mode === 'classic')
      return (
        <div key={key} className="font-semibold">
          {kids(element)}
        </div>
      )
    return (
      <div key={key} className={tag === 'h2' ? 'text-lg font-bold' : 'text-base font-semibold'}>
        {kids(element)}
      </div>
    )
  }
  if (tag === 'blockquote') {
    return (
      <blockquote
        key={key}
        className="border-l-[3px] border-[#3390ec] pl-2.5 dark:border-[#6ab3f3]"
      >
        {Array.from(element.children).map((child, index) => block(child, index, mode))}
        {element.children.length === 0 && kids(element)}
      </blockquote>
    )
  }
  if (tag === 'pre') {
    return (
      <pre
        key={key}
        className="overflow-x-auto rounded-md bg-black/10 p-2 font-mono text-[0.9em] dark:bg-white/10"
      >
        {element.textContent}
      </pre>
    )
  }
  return <p key={key}>{kids(element)}</p>
}

export function PostHtml({ html, mode }: { html: string; mode: Mode }) {
  const parsed = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html')
  return (
    <div className="space-y-3 break-words">
      {Array.from(parsed.body.children).map((child, index) => block(child, index, mode))}
    </div>
  )
}
