import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { useTourKeys } from './useTourKeys'

type Handlers = { onNext: () => void; onBack: () => void; onSkip: () => void }

function Tour({ handlers, hasNext }: { handlers: Handlers; hasNext: boolean }) {
  useTourKeys({
    onNext: hasNext ? handlers.onNext : undefined,
    onBack: handlers.onBack,
    onSkip: handlers.onSkip,
  })
  return (
    <>
      <h1 tabIndex={-1}>Шаг</h1>
      <input aria-label="Поле" />
      <div role="dialog" aria-label="Окно">
        <button type="button">Внутри окна</button>
      </div>
    </>
  )
}

function setup(hasNext = true) {
  const handlers = { onNext: vi.fn(), onBack: vi.fn(), onSkip: vi.fn() }
  render(<Tour handlers={handlers} hasNext={hasNext} />)
  return { user: userEvent.setup(), ...handlers }
}

describe('useTourKeys', () => {
  it('steps with the arrows, goes on with Enter and skips with Escape', async () => {
    const { user, onNext, onBack, onSkip } = setup()
    screen.getByRole('heading').focus()

    await user.keyboard('{ArrowRight}{Enter}{ArrowLeft}{Escape}')

    expect(onNext).toHaveBeenCalledTimes(2)
    expect(onBack).toHaveBeenCalledTimes(1)
    expect(onSkip).toHaveBeenCalledTimes(1)
  })

  it('leaves the keys to a field the reader types in and to a dialog', async () => {
    const { user, onNext, onBack, onSkip } = setup()

    await user.click(screen.getByRole('textbox', { name: 'Поле' }))
    await user.keyboard('{ArrowLeft}{ArrowRight}{Enter}{Escape}')
    screen.getByRole('button', { name: 'Внутри окна' }).focus()
    await user.keyboard('{Escape}{ArrowRight}')

    expect(onNext).not.toHaveBeenCalled()
    expect(onBack).not.toHaveBeenCalled()
    expect(onSkip).not.toHaveBeenCalled()
  })

  it('ignores the arrows with a modifier, such as a browser shortcut', async () => {
    const { user, onBack } = setup()

    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}')

    expect(onBack).not.toHaveBeenCalled()
  })

  it('does nothing ahead where there is no step ahead', async () => {
    const { user, onBack } = setup(false)

    await user.keyboard('{ArrowRight}{Enter}{ArrowLeft}')

    expect(onBack).toHaveBeenCalledTimes(1)
  })
})
