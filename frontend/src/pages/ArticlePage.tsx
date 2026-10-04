import { useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router'
import { ChevronLeft, ExternalLink, FileText } from '../components/icons'
import { ScrollTopButton } from '../components/ScrollTopButton'
import { buttonClass } from '../components/tokens'
import { Button, EmptyState, ErrorNote, ReadingTime, SkeletonBlock } from '../components/ui'
import { ArticleBlocks } from '../features/reader/ArticleBlocks'
import { ApiError } from '../lib/api'
import type { ArticleRead } from '../lib/api'
import { CATEGORY_LABELS, externalHref, formatDateTime } from '../lib/format'
import { useArticle } from '../lib/queries'

const isArticleId = (value: number) => Number.isInteger(value) && value > 0

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

type SourceLinkProps = { article: ArticleRead; label: string; className: string }

function SourceLink({ article, label, className }: SourceLinkProps) {
  return (
    <a
      href={externalHref(article.url)}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
    >
      <ExternalLink size={15} />
      {label}
    </a>
  )
}

function Loading() {
  return (
    <div aria-busy className="space-y-4">
      <span className="sr-only" role="status">
        Загружаем статью
      </span>
      <SkeletonBlock className="h-4 w-56" />
      <SkeletonBlock className="h-9 w-full" />
      <SkeletonBlock className="h-9 w-2/3" />
      <SkeletonBlock className="mt-6 h-64 w-full rounded-2xl" />
      {[0, 1, 2, 3].map((line) => (
        <SkeletonBlock key={line} className="h-4 w-full" />
      ))}
      <SkeletonBlock className="h-4 w-1/2" />
    </div>
  )
}

function NotFound() {
  return (
    <EmptyState icon={<FileText size={26} />} title="Статья не найдена">
      Возможно, источник удалили из каталога.
    </EmptyState>
  )
}

function Article({ article }: { article: ArticleRead }) {
  const host = hostOf(article.url)
  const heading = useRef<HTMLHeadingElement>(null)
  // The list it was opened from is gone: reading starts at the headline, and
  // a screen reader says where the reader is now.
  useEffect(() => heading.current?.focus({ preventScroll: true }), [])
  return (
    <article lang={article.language}>
      <header>
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{article.source_name}</span>
          <span>{CATEGORY_LABELS[article.source_category] ?? article.source_category}</span>
          <time dateTime={article.published_at}>{formatDateTime(article.published_at)}</time>
          <ReadingTime minutes={article.reading_minutes} />
        </div>
        <h1
          ref={heading}
          tabIndex={-1}
          className="mt-3 font-serif text-[28px] leading-[1.2] font-semibold tracking-tight text-balance text-foreground outline-none sm:text-[34px]"
        >
          {article.title}
        </h1>
        {article.author && <p className="mt-2.5 text-sm text-muted-foreground">{article.author}</p>}
      </header>

      {!article.complete && (
        <p className="mt-6 rounded-xl bg-surface-container px-4 py-3 text-sm text-muted-foreground">
          Сайт {host} не вернул страницу, поэтому показан только текст из ленты. Полная версия
          доступна в источнике.
        </p>
      )}

      {article.blocks.length > 0 ? (
        <div className="mt-6">
          <ArticleBlocks articleId={article.id} blocks={article.blocks} />
        </div>
      ) : (
        <EmptyState icon={<FileText size={26} />} title="Текста нет">
          В источнике был только заголовок. Статью можно открыть по ссылке на оригинал.
        </EmptyState>
      )}

      <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-outline-variant pt-5 text-sm text-muted-foreground">
        <p className="max-w-md">Текст и картинки со страницы {host}; права на них у источника.</p>
        <SourceLink
          article={article}
          label={`Читать на ${host}`}
          className={buttonClass('secondary', 'sm')}
        />
      </footer>
    </article>
  )
}

/** An article read inside the app: its text and pictures, with the way back to the list. */
export function ArticlePage() {
  const { articleId = '' } = useParams()
  const id = Number(articleId)
  const isValid = isArticleId(id)
  const article = useArticle(id, isValid)
  const navigate = useNavigate()
  // Opened from a list in the app: back to it, where the browser left it.
  // Opened first in this tab (by a link, or right after signing in): to the feed.
  const goBack = () => {
    const entry = window.history.state as { idx?: number } | null
    if ((entry?.idx ?? 0) > 0) navigate(-1)
    else navigate('/feed')
  }

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [id])

  const isMissing = !isValid || (article.error instanceof ApiError && article.error.status === 404)
  let content = <Loading />
  if (isMissing) content = <NotFound />
  else if (article.data) content = <Article key={article.data.id} article={article.data} />
  else if (article.error) content = <ErrorNote error={article.error} />

  return (
    <div className="mx-auto max-w-[720px]">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" icon={<ChevronLeft size={18} />} onClick={goBack}>
          Назад
        </Button>
        {article.data && !isMissing && (
          <SourceLink
            article={article.data}
            label="Оригинал"
            className={buttonClass('ghost', 'sm')}
          />
        )}
      </div>
      {content}
      <ScrollTopButton />
    </div>
  )
}
