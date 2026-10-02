import clsx from 'clsx'
import { Fragment, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../../lib/api'
import type { Block, Span } from '../../lib/api'
import { externalHref } from '../../lib/format'

// Smaller than this on both sides is an icon or a counter, not a picture to show.
const MIN_PICTURE_SIDE = 48
// An alt text this long describes the picture; a short one is only a name ("Fortinet").
const CAPTION_MIN_WORDS = 3

function Spans({ spans }: { spans: Span[] }) {
  return spans.map((span, index) => {
    let node: ReactNode = span.text
    if (span.code) {
      node = (
        <code className="rounded-md bg-surface-container px-1.5 py-0.5 font-mono text-[0.85em]">
          {node}
        </code>
      )
    }
    if (span.i) node = <em>{node}</em>
    if (span.b) node = <strong className="font-semibold">{node}</strong>
    const href = externalHref(span.href)
    if (href) {
      node = (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="text-primary underline decoration-primary/40 underline-offset-[3px] hover:decoration-primary"
        >
          {node}
        </a>
      )
    }
    return <Fragment key={index}>{node}</Fragment>
  })
}

function Picture({
  articleId,
  id,
  alt,
  isFirst,
}: {
  articleId: number
  id: string
  alt?: string
  isFirst: boolean
}) {
  const [isHidden, setIsHidden] = useState(false)
  if (isHidden) return null
  const caption = alt && alt.split(/\s+/).length >= CAPTION_MIN_WORDS ? alt : null
  return (
    <figure className="my-7">
      <img
        src={api.articleImageUrl(articleId, id)}
        // The caption says it already.
        alt={caption ? '' : (alt ?? '')}
        loading={isFirst ? 'eager' : 'lazy'}
        decoding="async"
        // A picture the site would not give is left out, not shown broken.
        onError={() => setIsHidden(true)}
        onLoad={(event) => {
          const { naturalWidth, naturalHeight } = event.currentTarget
          if (naturalWidth < MIN_PICTURE_SIDE && naturalHeight < MIN_PICTURE_SIDE) setIsHidden(true)
        }}
        className="mx-auto max-h-[75vh] w-auto max-w-full rounded-2xl bg-surface-container object-contain"
      />
      {caption && (
        <figcaption className="mt-2.5 text-center font-sans text-[13px] leading-snug text-muted-foreground">
          {caption}
        </figcaption>
      )}
    </figure>
  )
}

const HEADING_CLASS = {
  2: 'mt-10 mb-3 text-[24px] leading-tight',
  3: 'mt-8 mb-2.5 text-[20px] leading-snug',
  4: 'mt-7 mb-2 text-[18px] leading-snug',
  5: 'mt-6 mb-2 text-[16px] leading-snug',
} as const

function BlockView({
  block,
  articleId,
  isFirst,
}: {
  block: Block
  articleId: number
  isFirst: boolean
}) {
  switch (block.type) {
    case 'p':
      return (
        <p className="my-4 whitespace-pre-line">
          <Spans spans={block.spans} />
        </p>
      )
    case 'quote':
      return (
        <blockquote className="my-6 border-l-[3px] border-primary/60 pl-5 whitespace-pre-line text-foreground/85 italic">
          <Spans spans={block.spans} />
        </blockquote>
      )
    case 'h': {
      const Tag = `h${block.level}` as const
      return <Tag className={`font-semibold ${HEADING_CLASS[block.level]}`}>{block.text}</Tag>
    }
    case 'list': {
      const Tag = block.ordered ? 'ol' : 'ul'
      return (
        <Tag
          className={`my-4 space-y-1.5 pl-7 marker:text-muted-foreground ${block.ordered ? 'list-decimal' : 'list-disc'}`}
        >
          {block.items.map((spans, index) => (
            <li key={index} className="pl-1 whitespace-pre-line">
              <Spans spans={spans} />
            </li>
          ))}
        </Tag>
      )
    }
    case 'code':
      return (
        // Focusable: a long line scrolls from the keyboard too.
        <pre
          tabIndex={0}
          className="my-5 overflow-x-auto rounded-xl bg-surface-container px-4 py-3 font-mono text-[13px] leading-relaxed"
        >
          <code>{block.text}</code>
        </pre>
      )
    case 'image':
      return <Picture articleId={articleId} id={block.id} alt={block.alt} isFirst={isFirst} />
    case 'table':
      return (
        <div
          role="region"
          aria-label="Таблица"
          tabIndex={0}
          className="my-6 overflow-x-auto rounded-xl border border-outline-variant font-sans"
        >
          <table className="w-full border-collapse text-sm">
            {block.head && (
              <thead className="bg-surface-container">
                <tr>
                  {block.head.map((cell, index) => (
                    <th
                      key={index}
                      scope="col"
                      className="min-w-24 px-3 py-2 text-left font-semibold"
                    >
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {block.rows.map((row, index) => (
                <tr
                  key={index}
                  className={clsx(
                    'border-t border-outline-variant',
                    !block.head && 'first:border-t-0',
                  )}
                >
                  {row.map((cell, column) => (
                    // Hashes and paths break anywhere; a column stays wide enough for a word.
                    <td
                      key={column}
                      className="min-w-24 px-3 py-2 align-top [overflow-wrap:anywhere]"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
  }
}

/**
 * The article's text, drawn from plain blocks: no markup of the site reaches
 * the page, and its pictures come through the API.
 */
export function ArticleBlocks({ articleId, blocks }: { articleId: number; blocks: Block[] }) {
  return (
    // Long paths and addresses break where they must; code keeps its lines and scrolls.
    <div className="font-serif text-[17px] leading-[1.75] break-words text-foreground sm:text-[18px]">
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} articleId={articleId} isFirst={index === 0} />
      ))}
    </div>
  )
}
