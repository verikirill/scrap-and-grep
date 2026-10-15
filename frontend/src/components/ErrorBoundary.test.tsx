import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

let shouldFail = true

function Fragile() {
  if (shouldFail) throw new Error('chunk missing')
  return <p>Раздел работает</p>
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    shouldFail = true
    // React reports a caught render error on the console.
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('shows its children while they draw', () => {
    shouldFail = false
    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Раздел работает')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('puts a way out in place of a part that failed, under its own title', () => {
    render(
      <ErrorBoundary title="Лента не загрузилась">
        <Fragile />
      </ErrorBoundary>,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Лента не загрузилась')
    expect(alert).toHaveTextContent('Возможно, сервис обновился')
  })

  it('draws the part again on «Попробовать снова»', async () => {
    const user = userEvent.setup()
    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Раздел не загрузился')

    shouldFail = false
    await user.click(screen.getByRole('button', { name: 'Попробовать снова' }))

    expect(screen.getByText('Раздел работает')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  describe('reload', () => {
    const original = window.location
    afterEach(() => {
      Object.defineProperty(window, 'location', { configurable: true, value: original })
    })

    it('reloads the page on «Обновить страницу»', async () => {
      const reload = vi.fn()
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: { ...original, reload },
      })
      const user = userEvent.setup()
      render(
        <ErrorBoundary>
          <Fragile />
        </ErrorBoundary>,
      )

      await user.click(screen.getByRole('button', { name: 'Обновить страницу' }))

      expect(reload).toHaveBeenCalledOnce()
    })
  })
})
