import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { useMediaQuery } from './useMediaQuery'

describe('useMediaQuery', () => {
  it('tells whether the screen matches now and follows a resize both ways', () => {
    setMediaQueries({ '(min-width: 1024px)': true })
    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'))
    expect(result.current).toBe(true)

    act(() => setMediaQueries({ '(min-width: 1024px)': false }))
    expect(result.current).toBe(false)
    act(() => setMediaQueries({ '(min-width: 1024px)': true }))
    expect(result.current).toBe(true)
  })

  it('follows the query it is given now, not the first one', () => {
    setMediaQueries({ '(min-width: 1024px)': false, '(min-width: 640px)': true })
    const { result, rerender } = renderHook(({ query }) => useMediaQuery(query), {
      initialProps: { query: '(min-width: 1024px)' },
    })
    expect(result.current).toBe(false)

    rerender({ query: '(min-width: 640px)' })

    expect(result.current).toBe(true)
  })
})
