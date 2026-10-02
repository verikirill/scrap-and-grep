import { describe, expect, it } from 'vitest'
import type { Source } from './api'
import { groupSources, matchesSource, queryWords } from './sourceList'

function source(fields: Partial<Source>): Source {
  return {
    id: 1,
    slug: 'custom',
    name: 'Источник',
    kind: 'rss',
    feed_url: 'https://example.org/feed',
    site_url: null,
    category: 'security',
    language: 'ru',
    enabled: true,
    fetch_full_text: false,
    last_fetched_at: null,
    last_status: null,
    last_error: null,
    consecutive_failures: 0,
    articles: 0,
    articles_last_day: 0,
    ...fields,
  }
}

const channel = source({
  slug: 'tg-true_secator',
  name: 'SecAtor',
  kind: 'telegram',
  feed_url: 'https://t.me/s/true_secator',
  site_url: 'https://t.me/true_secator',
})
const bdu = source({
  slug: 'bdu-incident',
  name: 'БДУ ФСТЭК: уязвимости, используемые в атаках',
  feed_url: 'https://bdu.fstec.ru/ubi/vul/incident/rss',
  category: 'regulator',
})

describe('matchesSource', () => {
  it('finds a channel by its @name, its address or the word Telegram', () => {
    for (const query of ['@true_secator', 'TRUE_SECATOR', 't.me', 'телеграм', 'telegram']) {
      expect(matchesSource(channel, query)).toBe(true)
    }
    expect(matchesSource(bdu, 't.me')).toBe(false)
  })

  it('wants every word, in any case and with ё read as е', () => {
    expect(matchesSource(bdu, 'бду атаках')).toBe(true)
    expect(matchesSource(bdu, 'бду SecAtor')).toBe(false)
    // The category is searched too.
    expect(matchesSource(bdu, 'регуляторы')).toBe(true)
    expect(matchesSource(source({ name: 'Ещё один' }), 'еще')).toBe(true)
  })

  it('lets everything through an empty query', () => {
    expect(matchesSource(bdu, '   ')).toBe(true)
    // A lone @ is no word either, so the list is not counted as a search.
    expect(queryWords(' @ ')).toEqual([])
  })
})

describe('groupSources', () => {
  const xakep = source({ id: 2, name: 'Хакер', articles: 20 })
  const pt = source({ id: 3, name: 'PT: трендовые уязвимости', kind: 'pt_trending', articles: 10 })
  const quiet = source({ id: 4, name: 'Ещё канал', kind: 'telegram', articles: 2 })
  const all = [{ ...channel, articles: 15 }, bdu, xakep, pt, quiet]

  it('splits Telegram channels from sites, the PT page among the sites', () => {
    const groups = groupSources(all, 'kind', 'name')

    expect(groups.map((group) => group.label)).toEqual(['Сайты', 'Telegram-каналы'])
    expect(groups[1].sources.map((item) => item.name)).toEqual(['Ещё канал', 'SecAtor'])
    expect(groups[0].sources).toContain(pt)
  })

  it('puts the sources with more articles first or last, as asked', () => {
    const most = groupSources(all, 'kind', 'most')
    const least = groupSources(all, 'kind', 'least')

    expect(most[0].sources.map((item) => item.articles)).toEqual([20, 10, 0])
    expect(least[1].sources.map((item) => item.name)).toEqual(['Ещё канал', 'SecAtor'])
  })

  it('leaves out a category with nothing in it', () => {
    const groups = groupSources([bdu, xakep], 'category', 'name')

    expect(groups.map((group) => group.key)).toEqual(['security', 'regulator'])
  })
})
