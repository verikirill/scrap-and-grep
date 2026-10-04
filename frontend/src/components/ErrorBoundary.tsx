import { RotateCw, TriangleAlert } from './icons'
import { Component } from 'react'
import type { ReactNode } from 'react'
import { Button, Card } from './ui'

type Props = {
  children: ReactNode
  /** What to say in place of the part that failed. */
  title?: string
}

type State = { error: Error | null }

/**
 * A part of the page that failed to load or draw shows a way out instead of
 * blanking the whole app. The usual cause is a new release: an open tab asks
 * for a code chunk the server no longer has, and a reload fixes it.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  reset = () => this.setState({ error: null })

  render() {
    if (!this.state.error) return this.props.children
    return (
      <Card variant="outlined" className="p-6">
        <div role="alert" className="flex flex-col items-start gap-3">
          <TriangleAlert size={22} className="text-destructive" />
          <p className="text-base font-medium">{this.props.title ?? 'Раздел не загрузился'}</p>
          <p className="text-sm text-muted-foreground">
            Возможно, сервис обновился. Перезагрузите страницу; если ошибка повторится, попробуйте
            позже.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              variant="primary"
              icon={<RotateCw size={15} />}
              onClick={() => window.location.reload()}
            >
              Обновить страницу
            </Button>
            <Button variant="ghost" onClick={this.reset}>
              Попробовать снова
            </Button>
          </div>
        </div>
      </Card>
    )
  }
}
