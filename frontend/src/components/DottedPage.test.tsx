import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { DottedPage } from './DottedPage'

const isDark = () => document.documentElement.classList.contains('dark')

describe('DottedPage', () => {
  afterEach(() => document.documentElement.classList.remove('dark'))

  it('takes the theme the reader chose, though the switch lives in the app frame', () => {
    localStorage.setItem('radar-theme', 'dark')

    render(<DottedPage>Знакомство</DottedPage>)

    expect(screen.getByText('Знакомство')).toBeInTheDocument()
    expect(isDark()).toBe(true)
  })

  it('follows the system when the reader has not chosen, and goes light from dark', () => {
    document.documentElement.classList.add('dark')
    setMediaQueries({ '(prefers-color-scheme: dark)': false })

    render(<DottedPage>Знакомство</DottedPage>)

    expect(isDark()).toBe(false)
  })
})
