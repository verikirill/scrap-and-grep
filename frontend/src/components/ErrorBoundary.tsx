import { RotateCw } from './icons'
import { Component } from 'react'
import type { ReactNode } from 'react'
import { ErrorIllustration } from './ErrorIllustration'
import { buttonClass } from './tokens'
import { Button, Card, ErrorState } from './ui'

type Props = {
  children: ReactNode
  /**
   * What to say in place of a part of a page that failed: an alert inside the
   * page. Without it the boundary stands for the whole page, with the cat by
   * a pulled plug.
   */
  title?: string
}

type State = { error: Error | null }

const REASON =
  'Возможно, сервис обновился. Перезагрузите страницу, а если ошибка повторится, загляните чуть позже.'

/**
 * A page, or a part of one, that failed to load or draw shows a way out
 * instead of blanking the whole app. The usual cause is a new release: an open
 * tab asks for a code chunk the server no longer has, and a reload fixes it.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  reset = () => this.setState({ error: null })

  render() {
    if (!this.state.error) return this.props.children
    const reload = (
      <Button
        variant="primary"
        icon={<RotateCw size={15} />}
        onClick={() => window.location.reload()}
      >
        Обновить страницу
      </Button>
    )
    const retry = (
      <Button variant="ghost" onClick={this.reset}>
        Попробовать снова
      </Button>
    )
    if (this.props.title) {
      return (
        <Card variant="outlined">
          <ErrorState
            title={this.props.title}
            action={
              <>
                {reload}
                {retry}
              </>
            }
          >
            {REASON}
          </ErrorState>
        </Card>
      )
    }
    // A plain link: after a crash a fresh load of the home page is the surest way back.
    return (
      <div role="alert" className="flex flex-col items-center px-4 py-10 text-center">
        <ErrorIllustration status={500} />
        <h1 className="mt-6 text-xl font-semibold">Что-то сломалось</h1>
        <p className="mt-1.5 max-w-md text-sm text-muted">{REASON}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {reload}
          <a href="/" className={buttonClass('secondary')}>
            На главную
          </a>
          {retry}
        </div>
      </div>
    )
  }
}
