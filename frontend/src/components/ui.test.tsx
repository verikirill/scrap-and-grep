import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../lib/api'
import { BrandCat } from './BrandCat'
import {
  AnimatedNumber,
  Button,
  Chip,
  EmptyState,
  ErrorNote,
  ErrorState,
  Field,
  PageHeader,
  ReadingTime,
  Spinner,
  Toggle,
} from './ui'

describe('Button', () => {
  it('is a plain button that acts on a click', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>Сохранить</Button>)
    const button = screen.getByRole('button', { name: 'Сохранить' })
    expect(button).toHaveAttribute('type', 'button')
    await user.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('cannot be pressed twice while its action runs, and says it is busy', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button isBusy onClick={onClick}>
        Сохранить
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Сохранить' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('Spinner', () => {
  it('speaks only when it has a label', () => {
    const { rerender } = render(<Spinner />)
    expect(screen.queryByRole('status')).toBeNull()
    rerender(<Spinner label="Загружаем выпуск" />)
    expect(screen.getByRole('status', { name: 'Загружаем выпуск' })).toBeInTheDocument()
  })
})

describe('Chip', () => {
  it('tells what it means on hover when it has a hint', () => {
    render(
      <>
        <Chip hint="Есть в каталоге KEV">KEV</Chip>
        <Chip title="Оценка модели">0,82</Chip>
      </>,
    )
    expect(screen.getByText('KEV')).toHaveAttribute('title', 'Есть в каталоге KEV')
    expect(screen.getByText('0,82')).toHaveAttribute('title', 'Оценка модели')
  })
})

describe('Toggle', () => {
  function Setting({ disabled }: { disabled?: boolean }) {
    const [on, setOn] = useState(false)
    return <Toggle checked={on} onChange={setOn} label="Автопостинг" disabled={disabled} />
  }

  it('is a named switch that flips on a click', async () => {
    const user = userEvent.setup()
    render(<Setting />)
    const toggle = screen.getByRole('switch', { name: 'Автопостинг' })
    expect(toggle).not.toBeChecked()
    await user.click(toggle)
    expect(toggle).toBeChecked()
  })

  it('stays put while disabled', async () => {
    const user = userEvent.setup()
    render(<Setting disabled />)
    const toggle = screen.getByRole('switch', { name: 'Автопостинг' })
    await user.click(toggle)
    expect(toggle).not.toBeChecked()
  })
})

describe('Field', () => {
  it('labels the control inside it', () => {
    render(
      <Field label="Название" hint="до 80 символов">
        <input />
      </Field>,
    )
    expect(screen.getByRole('textbox', { name: /Название/ })).toBeInTheDocument()
    expect(screen.getByText('до 80 символов')).toBeInTheDocument()
  })

  it('becomes a named group around several controls', () => {
    render(
      <Field label="Ключевые слова" isGroup>
        <button type="button">Убрать «SCADA»</button>
        <input aria-label="Новое слово" />
      </Field>,
    )
    const group = screen.getByRole('group', { name: 'Ключевые слова' })
    expect(group).toContainElement(screen.getByRole('button', { name: 'Убрать «SCADA»' }))
  })
})

describe('ErrorNote', () => {
  it('shows an error’s message as an alert, and nothing without an error', () => {
    const { rerender } = render(<ErrorNote error={null} />)
    expect(screen.queryByRole('alert')).toBeNull()
    rerender(<ErrorNote error={new Error('Профиль не найден')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Профиль не найден')
    rerender(<ErrorNote error="boom" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Неизвестная ошибка')
  })
})

describe('ErrorState', () => {
  it('is one alert with a warning sign, what failed, why, and the way out', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    const { container } = render(
      <ErrorState
        title="Лента не загрузилась"
        error={new Error('Сервис недоступен')}
        action={<Button onClick={onRetry}>Повторить</Button>}
      >
        Попробуйте через минуту.
      </ErrorState>,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Лента не загрузилась')
    expect(alert).toHaveTextContent('Сервис недоступен')
    expect(alert).toHaveTextContent('Попробуйте через минуту.')
    // The sign sits in a danger-tinted tile, hidden from screen readers: the title says it.
    const tile = container.querySelector('.icon-tile')
    expect(tile).toHaveAttribute('data-tone', 'danger')
    expect(tile).toHaveAttribute('aria-hidden', 'true')
    expect(tile?.querySelector('svg')).not.toBeNull()
    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('says the error is unknown when it is not an Error, and only the title without one', () => {
    const { rerender } = render(<ErrorState title="Не открылось" error="boom" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Неизвестная ошибка')
    rerender(<ErrorState title="Не открылось" />)
    expect(screen.getByRole('alert')).toHaveTextContent(/^Не открылось$/)
  })

  it.each([
    [0, 'Нет связи с сервером', 'Проверьте подключение к интернету'],
    [401, 'Нет доступа', 'Войдите заново'],
    [403, 'Нет доступа', 'Войдите заново'],
    [404, 'Не нашлось', 'Возможно, это удалили'],
    [429, 'Слишком много запросов', 'Подождите немного'],
    [502, 'Сервис временно недоступен', 'Попробуйте ещё раз через минуту'],
  ])('names a request that failed with %i, and what to do', (status, title, hint) => {
    render(<ErrorState error={new ApiError(status, `Ошибка ${status}`)} />)
    expect(screen.getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(hint)
    expect(alert).not.toHaveTextContent(`Ошибка ${status}`)
    // Inside a page the sign stays a tile, whatever the status.
    expect(alert.querySelector('.icon-tile')).not.toBeNull()
    expect(alert.querySelector('img')).toBeNull()
  })

  it('keeps the caller’s title first and the server’s reason under the kind', () => {
    render(
      <ErrorState
        title="Лента не загрузилась"
        error={new ApiError(503, 'Индекс публикаций перестраивается')}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Лента не загрузилась' })).toBeInTheDocument()
    expect(screen.getByText('Сервис временно недоступен')).toBeInTheDocument()
    expect(screen.getByText('Индекс публикаций перестраивается')).toBeInTheDocument()
  })

  it('shows any other refusal in the server’s words, under a general title without one', () => {
    render(<ErrorState error={new ApiError(409, 'Источник уже добавлен.')} />)
    expect(screen.getByRole('heading', { name: 'Что-то пошло не так' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Источник уже добавлен.')
  })

  it.each([
    [503, '/brand/errors/503.webp'],
    [500, '/brand/errors/503.webp'],
    [429, '/brand/errors/429.webp'],
  ])('fills a page that failed with %i with its drawing and a page heading', (status, src) => {
    render(
      <ErrorState isPage title="Не получилось проверить вход" error={new ApiError(status, 'x')} />,
    )
    const alert = screen.getByRole('alert')
    const art = alert.querySelector('img')
    expect(art).toHaveAttribute('src', src)
    expect(art).toHaveAttribute('alt', '')
    expect(art).toHaveAttribute('loading', 'lazy')
    expect(alert.querySelector('.icon-tile')).toBeNull()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Не получилось проверить вход' }),
    ).toBeInTheDocument()
  })

  it('keeps the tile on a page that failed for a reason without a drawing', () => {
    render(<ErrorState isPage error={new ApiError(0, 'x')} />)
    const alert = screen.getByRole('alert')
    expect(alert.querySelector('img')).toBeNull()
    expect(alert.querySelector('.icon-tile')).not.toBeNull()
    expect(screen.getByRole('heading', { level: 1, name: 'Нет связи с сервером' })).toBeVisible()
  })
})

describe('ReadingTime', () => {
  it('names the minutes, and stays away while they are not known', () => {
    const { rerender } = render(<ReadingTime minutes={4} />)
    expect(screen.getByText('4 мин чтения')).toBeInTheDocument()
    rerender(<ReadingTime minutes={null} />)
    expect(screen.queryByText(/мин чтения/)).toBeNull()
    rerender(<ReadingTime minutes={0} />)
    expect(screen.queryByText(/мин чтения/)).toBeNull()
  })
})

describe('AnimatedNumber', () => {
  it('ends on the new value, grouped as Russian numbers are', async () => {
    const { rerender } = render(<AnimatedNumber value={12} />)
    expect(screen.getByText('12')).toBeInTheDocument()
    rerender(<AnimatedNumber value={12500} />)
    expect(await screen.findByText(/^12\s500$/)).toBeInTheDocument()
  })
})

describe('EmptyState and PageHeader', () => {
  it('names an empty place and offers the step that fills it', () => {
    render(
      <EmptyState
        icon={<span />}
        title="Выпусков пока нет"
        action={<Button>Собрать выпуск</Button>}
      >
        Соберите первый выпуск.
      </EmptyState>,
    )
    expect(screen.getByRole('heading', { name: 'Выпусков пока нет' })).toBeInTheDocument()
    expect(screen.getByText('Соберите первый выпуск.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Собрать выпуск' })).toBeInTheDocument()
  })

  it('pictures an empty place with its topic icon in a soft tile, as decoration', () => {
    const { container } = render(
      <EmptyState icon={<svg data-testid="topic" />} title="Постов пока нет" />,
    )
    const tile = container.querySelector('.icon-tile')
    expect(tile).toHaveAttribute('data-tone', 'accent')
    expect(tile).toHaveAttribute('aria-hidden', 'true')
    expect(tile).toContainElement(screen.getByTestId('topic'))
    // Only the words are read.
    expect(screen.getByRole('heading')).toHaveAccessibleName('Постов пока нет')
  })

  it('puts a picture in place of the tile when given one', () => {
    const { container } = render(
      <EmptyState art={<BrandCat size={160} />} title="Выпусков пока нет" />,
    )
    expect(container.querySelector('.icon-tile')).toBeNull()
    expect(container.querySelector('.brand-cat')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByRole('heading')).toHaveAccessibleName('Выпусков пока нет')
  })

  it('gives the main action of a screen an arrow, keeping its name', () => {
    render(<Button variant="cta">Собрать выпуск</Button>)
    const button = screen.getByRole('button', { name: 'Собрать выпуск' })
    expect(button).toHaveClass('cta')
    expect(button.querySelector('.cta__arrow')).toHaveAttribute('aria-hidden', 'true')
  })

  it('heads a page with its title, line and actions', () => {
    render(
      <PageHeader
        title="Источники"
        subtitle="Откуда берутся статьи"
        actions={<Button>Добавить</Button>}
      />,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Источники' })).toBeInTheDocument()
    expect(screen.getByText('Откуда берутся статьи')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Добавить' })).toBeInTheDocument()
  })
})
