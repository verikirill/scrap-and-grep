import { describe, expect, it } from 'vitest'
import { safeLink } from './postText'

describe('safeLink', () => {
  it('lets through pages and Telegram links', () => {
    expect(safeLink('https://t.me/radar_demo/1')).toBe('https://t.me/radar_demo/1')
    expect(safeLink('tg://resolve?domain=radar_demo')).toBe('tg://resolve?domain=radar_demo')
  })

  it('drops what would run code or carry a page of its own', () => {
    // Feed data reaches these links: an article address is whatever a site wrote.
    for (const url of ['javascript:alert(1)', ' javascript:alert(1)', 'data:text/html,<b>', '']) {
      expect(safeLink(url)).toBeUndefined()
    }
    expect(safeLink(null)).toBeUndefined()
  })
})
