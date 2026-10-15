import type { Audience } from './api'

const BOTH: readonly Audience[] = ['specialist', 'management']
const SPECIALIST: readonly Audience[] = ['specialist']
const MANAGEMENT: readonly Audience[] = ['management']

/**
 * Blocks of the digest page around its entries a reader may hide, as the
 * backend keys them (radar.domain.DigestBlockKey), in the page's order. The
 * entries, the title and "Главное" are not in the list: they always stay.
 */
export const DIGEST_BLOCKS = [
  { key: 'implications', label: 'Что это значит для нас', audiences: MANAGEMENT },
  { key: 'funnel', label: 'Цифры выпуска', audiences: BOTH },
  { key: 'manual', label: 'Вместо ручной работы', audiences: BOTH },
  { key: 'method', label: 'Как составлен выпуск', audiences: BOTH },
  { key: 'soc_export', label: 'Выгрузка для SOC', audiences: SPECIALIST },
  { key: 'briefing', label: 'Голосовой брифинг', audiences: MANAGEMENT },
  { key: 'plan', label: 'План на смену', audiences: SPECIALIST },
  { key: 'changes', label: 'Что изменилось', audiences: SPECIALIST },
  { key: 'numbers', label: 'Период в цифрах', audiences: MANAGEMENT },
  { key: 'risk_matrix', label: 'Матрица риска', audiences: SPECIALIST },
  { key: 'short', label: 'Короткое видео', audiences: BOTH },
  { key: 'cve_timeline', label: 'Хронология уязвимостей', audiences: SPECIALIST },
  { key: 'rejected', label: 'Не вошло в выпуск', audiences: BOTH },
  { key: 'ask', label: 'Спросить выпуск', audiences: BOTH },
] as const

export type DigestBlockKey = (typeof DIGEST_BLOCKS)[number]['key']
export type DigestBlock = (typeof DIGEST_BLOCKS)[number]

/** The blocks an issue of this format has, in the page's order. */
export function blocksFor(audience: Audience): DigestBlock[] {
  return DIGEST_BLOCKS.filter((block) => block.audiences.includes(audience))
}

/** Whether the reader keeps this block of the issue; every block shows by default. */
export function isShown(
  digest: { hidden_digest_blocks?: readonly DigestBlockKey[] },
  key: DigestBlockKey,
): boolean {
  return !digest.hidden_digest_blocks?.includes(key)
}

/** The hidden blocks with one more hidden or shown again, in the page's order. */
export function withHiddenBlock(
  hidden: readonly DigestBlockKey[],
  key: DigestBlockKey,
  isHidden: boolean,
): DigestBlockKey[] {
  const next = new Set(hidden)
  if (isHidden) next.add(key)
  else next.delete(key)
  return DIGEST_BLOCKS.map((block) => block.key).filter((item) => next.has(item))
}
