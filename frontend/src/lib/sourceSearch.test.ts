import { describe, expect, it } from 'vitest'
import type { Source } from './api'
import { matchesSource } from './sourceSearch'

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
  })
})
