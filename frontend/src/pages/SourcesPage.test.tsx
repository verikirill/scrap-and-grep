import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  makeArticlesPage,
  makeMe,
  makeMeta,
  makeSourceHealth,
  makeSources,
  makeTimeline,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { SourcesPage } from './SourcesPage'

beforeEach(() => {
  server.use(
    http.get(apiUrl('/sources'), () => HttpResponse.json(makeSources(3))),
    http.get(apiUrl('/sources/health'), () => HttpResponse.json(makeSourceHealth())),
    http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({})),
    http.get(apiUrl('/articles'), () => HttpResponse.json(makeArticlesPage())),
    http.get(apiUrl('/articles/timeline'), () => HttpResponse.json(makeTimeline(14))),
  )
})

const section = (name: string) =>
  screen.getByRole('button', { name, current: name === 'Источники' ? 'page' : false })

/** The catalogue is the last part of the sources tab to arrive. */
const catalogue = () => screen.findByRole('link', { name: 'Минэнерго России' })
const healthSummary = () =>
  screen.findByText(
    (_, node) => node?.tagName === 'P' && /^Источники за сутки:/.test(node.textContent ?? ''),
  )

describe('SourcesPage', () => {
  it('opens on the catalogue with its health, and switches to the articles and back', async () => {
    const { user } = renderWithProviders(<SourcesPage />, { route: '/sources' })
    await catalogue()
    await healthSummary()
    expect(section('Источники')).toHaveAttribute('aria-current', 'page')

    await user.click(screen.getByRole('button', { name: 'Публикации' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/sources?tab=articles')
    expect(screen.getByRole('button', { name: 'Публикации' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(
      await screen.findByRole('searchbox', { name: 'Поиск по публикациям' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('searchbox', { name: 'Поиск по источникам' })).toBeNull()
    await screen.findByText(/^Всего:/)

    await user.click(screen.getByRole('button', { name: 'Источники' }))

    expect(screen.getByTestId('location')).toHaveTextContent(/^\/sources$/)
    await catalogue()
  })

  it('opens the articles straight from the address', async () => {
    renderWithProviders(<SourcesPage />, { route: '/sources?tab=articles' })

    expect(
      await screen.findByRole('searchbox', { name: 'Поиск по публикациям' }),
    ).toBeInTheDocument()
    await screen.findByText(/^Всего:/)
  })

  it('lets an administrator poll the whole catalogue and add sources', async () => {
    server.use(http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe({ is_admin: true }))))
    renderWithProviders(<SourcesPage />)
    await catalogue()

    expect(await screen.findByRole('button', { name: 'Опросить сейчас' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Добавить источник' })).toBeInTheDocument()
    await healthSummary()
  })

  it('lets a reader add sources to an open catalogue, but not poll all of it', async () => {
    server.use(http.get(apiUrl('/meta'), () => HttpResponse.json(makeMeta({ open_catalog: true }))))
    renderWithProviders(<SourcesPage />)
    await catalogue()

    expect(await screen.findByText(/^Добавить можно любой сайт или канал/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Добавить источник' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Опросить сейчас' })).toBeNull()
    await healthSummary()
  })

  it('tells a reader of a closed catalogue that only an administrator manages it', async () => {
    renderWithProviders(<SourcesPage />)
    await catalogue()

    expect(
      await screen.findByText('Включать и отключать источники может только администратор.'),
    ).toBeInTheDocument()
    // The add button is hidden by a class only, which jsdom does not apply: not asserted here.
    await healthSummary()
  })

  it('says why the catalogue could not be loaded', async () => {
    server.use(
      http.get(apiUrl('/sources'), () =>
        HttpResponse.json({ detail: 'Каталог недоступен.' }, { status: 503 }),
      ),
    )
    renderWithProviders(<SourcesPage />)

    expect(await screen.findByText('Каталог недоступен.')).toBeInTheDocument()
    expect(screen.getByText('Сервис временно недоступен')).toBeInTheDocument()
    await healthSummary()
  })
})
