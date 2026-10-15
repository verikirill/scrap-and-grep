import { useState } from 'react'
import type { ArticleRead, Block } from '../../lib/api'
import { useArticleTranslation } from '../../lib/queries'
import { readPrefersOriginal, writePrefersOriginal } from './translationChoice'

const UNAVAILABLE = 'Перевод сейчас недоступен.'

/** What the reader shows of a foreign article, and the bar that switches it. */
export type ArticleText =
  | { state: 'native' }
  | { state: 'translating'; source: 'en' | 'zh' }
  | {
      state: 'translated'
      source: 'en' | 'zh'
      title: string
      blocks: Block[]
      keptOriginal: number
    }
  | { state: 'original'; source: 'en' | 'zh' }
  | { state: 'unavailable'; source: 'en' | 'zh'; reason: string }

/**
 * An English or Chinese article is shown in Russian unless the reader last
 * chose the original; the choice is kept per browser. A few fragments the
 * model could not translate faithfully may stay in the original. A translation that
 * cannot be made now leaves the original in place with a note why.
 */
export function useArticleText(article: ArticleRead) {
  const source =
    article.text_language === 'en' || article.text_language === 'zh' ? article.text_language : null
  const [prefersOriginal, setPrefersOriginal] = useState(readPrefersOriginal)
  const translation = useArticleTranslation(article.id, source !== null && !prefersOriginal)

  const choose = (original: boolean) => {
    setPrefersOriginal(original)
    writePrefersOriginal(original)
  }

  let text: ArticleText = { state: 'native' }
  const found = translation.data
  if (source === null) return { text, choose }
  if (prefersOriginal) text = { state: 'original', source }
  else if (translation.isError) text = { state: 'unavailable', source, reason: UNAVAILABLE }
  else if (!found) text = { state: 'translating', source }
  else if (found.status === 'translated' && found.title !== null && found.blocks !== null) {
    text = {
      state: 'translated',
      source,
      title: found.title,
      blocks: found.blocks,
      keptOriginal: found.kept_original,
    }
  } else if (found.status === 'unavailable') {
    text = { state: 'unavailable', source, reason: found.reason ?? UNAVAILABLE }
  }
  return { text, choose }
}
