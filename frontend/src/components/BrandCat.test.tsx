import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BrandCat } from './BrandCat'

const sources = (root: Element) =>
  [...root.querySelectorAll('img')].map((img) => img.getAttribute('src'))

describe('BrandCat', () => {
  it('is drawn from the logo parts, all hidden from assistive tech', () => {
    const { container } = render(<BrandCat size={160} />)
    const cat = container.firstElementChild as HTMLElement

    expect(cat).toHaveAttribute('aria-hidden', 'true')
    expect(cat).toHaveAttribute('data-pose', 'search')
    expect(cat.style.width).toBe('160px')
    const images = [...cat.querySelectorAll('img')]
    expect(images).toHaveLength(11)
    for (const image of images) {
      expect(image).toHaveAttribute('alt', '')
      expect(image).toHaveAttribute('aria-hidden', 'true')
      expect(image).toHaveAttribute('draggable', 'false')
      expect(image).toHaveAttribute('decoding', 'async')
    }
    // Tail first, glass last: the order the parts overlap in.
    expect(sources(cat)[0]).toBe('/brand/cat/tail.webp')
    expect(sources(cat).at(-1)).toBe('/brand/cat/glass.webp')
    // Placed in percentages of the 640 by 660 scene, so it scales with the box.
    const paper = cat.querySelector('img[src="/brand/cat/paper.webp"]') as HTMLElement
    expect(paper.style.left).toBe(`${(170 / 640) * 100}%`)
    expect(paper.style.height).toBe(`${(288 / 660) * 100}%`)
  })

  it('searching, keeps its eyes open and the closed ones ready to blink', () => {
    const { container } = render(<BrandCat />)
    const eyes = sources(container).filter((src) => src?.includes('/eye-'))
    expect(eyes).toEqual([
      '/brand/cat/eye-left.webp',
      '/brand/cat/eye-right.webp',
      '/brand/cat/eye-left-closed.webp',
      '/brand/cat/eye-right-closed.webp',
    ])
  })

  it('asleep, has only its eyes closed', () => {
    const { container } = render(<BrandCat pose="sleep" />)
    expect(container.firstElementChild).toHaveAttribute('data-pose', 'sleep')
    const eyes = sources(container).filter((src) => src?.includes('/eye-'))
    expect(eyes).toEqual(['/brand/cat/eye-left-closed.webp', '/brand/cat/eye-right-closed.webp'])
  })
})
