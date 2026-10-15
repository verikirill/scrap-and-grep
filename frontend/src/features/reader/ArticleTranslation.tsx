import type { ReactNode } from 'react'
import { Language } from '../../components/icons'
import { Loading, Skeleton, SkeletonText } from '../../components/loading'
import type { ArticleText } from './useArticleText'

const FROM: Record<'en' | 'zh', string> = { en: 'английского', zh: 'китайского' }
const IN: Record<'en' | 'zh', string> = { en: 'английском', zh: 'китайском' }

function Switch({ children, onClick }: { children: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-medium text-accent decoration-accent/40 underline-offset-4 hover:underline"
    >
      {children}
    </button>
  )
}

/** A quiet line above the article: what language it is shown in, and the way to the other. */
export function TranslationBar({
  text,
  onChoose,
}: {
  text: ArticleText
  onChoose: (original: boolean) => void
}) {
  if (text.state === 'native') return null
  let note = `Переведено с ${FROM[text.source]}`
  let action = <Switch onClick={() => onChoose(true)}>Показать оригинал</Switch>
  if (text.state === 'translating') note = `Переводим с ${FROM[text.source]}`
  if (text.state === 'original') {
    note = `Оригинал на ${IN[text.source]}`
    action = <Switch onClick={() => onChoose(false)}>Показать перевод</Switch>
  }
  if (text.state === 'unavailable') return <Bar>{`${text.reason} Показан оригинал.`}</Bar>
  return (
    <Bar>
      <span>{note}</span>
      <span aria-hidden>·</span>
      {action}
    </Bar>
  )
}

function Bar({ children }: { children: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl bg-surface-secondary px-4 py-2.5 text-sm text-muted">
      <Language size={16} aria-hidden className="shrink-0" />
      {children}
    </div>
  )
}

/** The headline and paragraphs to come, while the model translates them. */
export function TranslatingSkeleton() {
  return (
    <Loading label="Переводим статью" className="mt-3">
      <Skeleton className="h-9 w-full" />
      <Skeleton className="mt-2 h-9 w-2/3" />
      <div className="mt-8 space-y-6">
        <SkeletonText lines={4} />
        <Skeleton className="h-6 w-1/2" />
        <SkeletonText lines={5} />
        <SkeletonText lines={3} />
      </div>
    </Loading>
  )
}
