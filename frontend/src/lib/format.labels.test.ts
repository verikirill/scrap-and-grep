import { describe, expect, it } from 'vitest'
import { externalHref, formatMegabytes, formatRelative, modelLabel, plural } from './format'

describe('externalHref', () => {
  it('keeps plain web links', () => {
    expect(externalHref('https://example.org/post?id=1')).toBe('https://example.org/post?id=1')
    expect(externalHref('http://example.org/')).toBe('http://example.org/')
  })

  it('drops what could run code or is not a link at all', () => {
    expect(externalHref('javascript:alert(1)')).toBeUndefined()
    expect(externalHref(' JavaScript:alert(1)')).toBeUndefined()
    expect(externalHref('data:text/html,<script>alert(1)</script>')).toBeUndefined()
    expect(externalHref('/relative/path')).toBeUndefined()
    expect(externalHref('')).toBeUndefined()
    expect(externalHref(null)).toBeUndefined()
    expect(externalHref(undefined)).toBeUndefined()
  })
})

describe('modelLabel', () => {
  it('names a model as a reader would, and the fallbacks without one', () => {
    expect(modelLabel('ollama:qwen3:8b')).toBe('qwen3:8b')
    expect(modelLabel('gpt-oss-120b')).toBe('gpt-oss-120b')
    expect(modelLabel('hashing-1024')).toBe('без модели (n-граммы)')
    expect(modelLabel('heuristic')).toBe('без модели (эвристика)')
    expect(modelLabel(undefined)).toBe('н/д')
    expect(modelLabel('')).toBe('н/д')
  })
})

describe('formatRelative', () => {
  const now = Date.parse('2026-10-14T12:00:00Z')

  it('says «только что» under a minute', () => {
    expect(formatRelative('2026-10-14T11:59:31Z', now)).toBe('только что')
  })

  it('counts minutes, hours and days back and ahead', () => {
    expect(formatRelative('2026-10-14T11:55:00Z', now)).toBe('5 минут назад')
    expect(formatRelative('2026-10-14T09:00:00Z', now)).toBe('3 часа назад')
    expect(formatRelative('2026-10-13T12:00:00Z', now)).toBe('вчера')
    expect(formatRelative('2026-10-11T12:00:00Z', now)).toBe('3 дня назад')
    expect(formatRelative('2026-10-14T14:00:00Z', now)).toBe('через 2 часа')
  })
})

describe('formatMegabytes', () => {
  it('shows a file size in decimal megabytes with one Russian decimal', () => {
    expect(formatMegabytes(5_000_000)).toBe('5 МБ')
    expect(formatMegabytes(5_240_000)).toBe('5,2 МБ')
    expect(formatMegabytes(120_000)).toBe('0,1 МБ')
  })
})

describe('plural', () => {
  const forms: [string, string, string] = ['запись', 'записи', 'записей']

  it('picks the Russian form by the last digits', () => {
    expect(plural(1, forms)).toBe('запись')
    expect(plural(21, forms)).toBe('запись')
    expect(plural(3, forms)).toBe('записи')
    expect(plural(24, forms)).toBe('записи')
    expect(plural(5, forms)).toBe('записей')
    expect(plural(0, forms)).toBe('записей')
  })

  it('takes the many form from 11 to 14, however they end', () => {
    expect(plural(11, forms)).toBe('записей')
    expect(plural(12, forms)).toBe('записей')
    expect(plural(14, forms)).toBe('записей')
    expect(plural(111, forms)).toBe('записей')
    expect(plural(112, forms)).toBe('записей')
  })
})
