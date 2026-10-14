import { keepPreviousData } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../lib/api'
import type { Channel, Defaults, Post } from '../lib/publishing'
import { keys } from '../lib/queries'
import {
  makeArticleBrief,
  makeBot,
  makeChannel,
  makeMe,
  makePost,
  makeProfile,
  makePublishingDefaults,
} from '../test/fixtures'
import { NEWS } from '../test/fixtures/catalog'
import { createTestQueryClient, renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { ChannelsPage } from './ChannelsPage'

const ADMIN_NOTE =
  'Публикация выключена, потому что на сервере не задан ключ шифрования токенов ботов.'
const READER_NOTE =
  'Публикация в Telegram на этом стенде пока выключена. Включить её может администратор.'

const ENERGY = makeChannel()
const SOC = makeChannel({
  id: 'channel-2',
  chat_id: -1003344556677,
  username: 'soc_news',
  title: 'Новости SOC',
})
const GRID = makeChannel({
  id: 'channel-3',
  chat_id: -1004455667788,
  username: 'grid_alerts',
  title: 'Сетевые тревоги',
})

/** A post of a channel about one of the catalogue's stories: its link names the story. */
function postAbout(channel: Channel, story: number): Post {
  const news = NEWS[story]
  return makePost({
    channel_id: channel.id,
    articles: [makeArticleBrief({ title: news.title, url: news.url })],
  })
}

const ENERGY_POST = postAbout(ENERGY, 0)
const SOC_POST = postAbout(SOC, 1)
const GRID_POST = postAbout(GRID, 2)
const storyLink = (post: Post) => ({ name: new RegExp(post.articles[0].title) })

/**
 * The publishing API of one reader: the defaults, a bot, the channels and
 * their posts. A channel removed takes its posts with it.
 */
function servePage({
  defaults = makePublishingDefaults(),
  channels = [ENERGY],
  posts = [],
}: { defaults?: Defaults; channels?: Channel[]; posts?: Post[] } = {}) {
  let listed = channels
  let queue = posts
  const postQueries: string[] = []
  server.use(
    http.get(apiUrl('/publishing/defaults'), () => HttpResponse.json(defaults)),
    http.get(apiUrl('/publishing/bots'), () => HttpResponse.json([makeBot()])),
    http.get(apiUrl('/publishing/channels'), () => HttpResponse.json(listed)),
    http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile()])),
    http.get(apiUrl('/publishing/posts'), ({ request }) => {
      const url = new URL(request.url)
      postQueries.push(url.search)
      const channelId = url.searchParams.get('channel_id')
      return HttpResponse.json(
        channelId ? queue.filter((post) => post.channel_id === channelId) : queue,
      )
    }),
    http.delete(apiUrl('/publishing/channels/:id'), ({ params }) => {
      listed = listed.filter((channel) => channel.id !== params.id)
      queue = queue.filter((post) => post.channel_id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return postQueries
}

/**
 * The page as the app shows it: the reader is known before any page opens
 * (RequireAuth waits for the account), so the account is in the cache.
 */
function renderPage(me: Me = makeMe(), client = createTestQueryClient()) {
  client.setQueryData(keys.me, me)
  return renderWithProviders(<ChannelsPage />, { route: '/channels', client })
}

/** The bot, the channel's audience and the empty queue: every request answered. */
async function findSettledPage() {
  expect(await screen.findByText('@energy_infosec_bot')).toBeInTheDocument()
  expect(
    await screen.findByRole('button', { name: /Аудитория канала: Инженер АСУ ТП/ }),
  ).toBeInTheDocument()
  expect(await screen.findByText('Постов пока нет')).toBeInTheDocument()
}

const channelSwitch = () => screen.getByRole('radiogroup', { name: 'Канал' })

describe('ChannelsPage', () => {
  it('tells an administrator that publishing waits for the key that encrypts bot tokens', async () => {
    servePage({ defaults: makePublishingDefaults({ enabled: false }) })
    renderPage(makeMe({ is_admin: true }))

    expect(await screen.findByText(ADMIN_NOTE)).toBeInTheDocument()
    expect(screen.queryByText(READER_NOTE)).toBeNull()
    await findSettledPage()
  })

  it.each([
    ['a reader', makeMe()],
    ['the administrator of the demo', makeMe({ is_admin: true, is_demo: true })],
  ])('tells %s only that publishing is off', async (_who, me) => {
    servePage({ defaults: makePublishingDefaults({ enabled: false }) })
    renderPage(me)

    expect(await screen.findByText(READER_NOTE)).toBeInTheDocument()
    expect(screen.queryByText(ADMIN_NOTE)).toBeNull()
    await findSettledPage()
  })

  it('says that posts go to the Telegram emulator on a test stand, and offers no channel switch for one channel', async () => {
    servePage({ defaults: makePublishingDefaults({ mock: true }) })
    renderPage()

    expect(
      await screen.findByText(/Стенд подключён к тестовому эмулятору Telegram/),
    ).toBeInTheDocument()
    await findSettledPage()
    expect(screen.queryByText(READER_NOTE)).toBeNull()
    expect(screen.queryByRole('radiogroup', { name: 'Канал' })).toBeNull()
  })

  it('shows the steps to connect a first channel', async () => {
    servePage({ channels: [] })
    renderPage()

    expect(await screen.findByText('Каналов пока нет')).toBeInTheDocument()
    const steps = screen
      .getAllByRole('listitem')
      .map((item) => item.textContent)
      .filter((text) => /^\d/.test(text ?? ''))
    expect(steps).toEqual([
      '1Создайте бота у @BotFather и вставьте его токен в блок «Боты»',
      '2Добавьте бота администратором в свой канал',
      '3Нажмите «Добавить канал» и выберите тон и расписание',
    ])
    expect(await screen.findByText('@energy_infosec_bot')).toBeInTheDocument()
    expect(await screen.findByText('Постов пока нет')).toBeInTheDocument()
    expect(screen.queryByText(/Стенд подключён/)).toBeNull()
  })

  it('narrows the queue to a channel chosen on the switch or by its card, and back to all', async () => {
    const postQueries = servePage({ channels: [ENERGY, SOC], posts: [ENERGY_POST, SOC_POST] })
    const { user } = renderPage()
    expect(await screen.findByRole('link', storyLink(SOC_POST))).toBeInTheDocument()
    expect(screen.getByRole('link', storyLink(ENERGY_POST))).toBeInTheDocument()
    expect(within(channelSwitch()).getByRole('radio', { name: 'Все' })).toBeChecked()

    await user.click(within(channelSwitch()).getByRole('radio', { name: 'Новости SOC' }))

    expect(await screen.findByRole('link', storyLink(SOC_POST))).toBeInTheDocument()
    expect(screen.queryByRole('link', storyLink(ENERGY_POST))).toBeNull()
    expect(screen.getByRole('button', { name: /Новости SOC/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(screen.getByRole('button', { name: /Энергетика и ИБ/ }))

    expect(await screen.findByRole('link', storyLink(ENERGY_POST))).toBeInTheDocument()
    expect(screen.queryByRole('link', storyLink(SOC_POST))).toBeNull()
    expect(within(channelSwitch()).getByRole('radio', { name: 'Энергетика и ИБ' })).toBeChecked()

    // The pressed card lets go of the filter.
    await user.click(screen.getByRole('button', { name: /Энергетика и ИБ/ }))

    expect(await screen.findByRole('link', storyLink(SOC_POST))).toBeInTheDocument()
    expect(within(channelSwitch()).getByRole('radio', { name: 'Все' })).toBeChecked()
    await waitFor(() =>
      expect(postQueries).toEqual([
        '?limit=100',
        '?channel_id=channel-2&limit=100',
        '?channel_id=channel-1&limit=100',
        '?limit=100',
      ]),
    )
    expect(
      await screen.findAllByRole('button', { name: /Аудитория канала: Инженер АСУ ТП/ }),
    ).toHaveLength(2)
  })

  it('never shows the posts of all channels in place of the chosen channel’s while they load', async () => {
    servePage({ channels: [ENERGY, SOC], posts: [ENERGY_POST, SOC_POST] })
    let answer: () => void = () => {}
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    let isAsked = false
    server.use(
      http.get(apiUrl('/publishing/posts'), async ({ request }) => {
        if (new URL(request.url).searchParams.get('channel_id') !== 'channel-2') return undefined
        isAsked = true
        await answered
        return HttpResponse.json([SOC_POST])
      }),
    )
    // The app's client keeps the previous answer on screen while the next one loads.
    const client = createTestQueryClient()
    client.setDefaultOptions({
      ...client.getDefaultOptions(),
      queries: { ...client.getDefaultOptions().queries, placeholderData: keepPreviousData },
    })
    const { user } = renderPage(makeMe(), client)
    expect(await screen.findByRole('link', storyLink(ENERGY_POST))).toBeInTheDocument()

    await user.click(within(channelSwitch()).getByRole('radio', { name: 'Новости SOC' }))

    await waitFor(() => expect(isAsked).toBe(true))
    expect(screen.queryByRole('link', storyLink(ENERGY_POST))).toBeNull()
    expect(screen.queryByRole('link', storyLink(SOC_POST))).toBeNull()
    answer()
    expect(await screen.findByRole('link', storyLink(SOC_POST))).toBeInTheDocument()
    expect(screen.queryByRole('link', storyLink(ENERGY_POST))).toBeNull()
  })

  it('puts the queue back on all channels when the chosen channel is disconnected', async () => {
    servePage({
      channels: [ENERGY, SOC, GRID],
      posts: [ENERGY_POST, SOC_POST, GRID_POST],
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderPage()
    await user.click(await screen.findByRole('radio', { name: 'Сетевые тревоги' }))
    expect(await screen.findByRole('link', storyLink(GRID_POST))).toBeInTheDocument()
    expect(screen.queryByRole('link', storyLink(ENERGY_POST))).toBeNull()

    // The cards come in the order of the channels: the third is the one chosen.
    await user.click(screen.getAllByRole('button', { name: 'Отключить канал' })[2])

    await waitFor(() => expect(screen.queryByRole('radio', { name: 'Сетевые тревоги' })).toBeNull())
    expect(within(channelSwitch()).getByRole('radio', { name: 'Все' })).toBeChecked()
    expect(await screen.findByRole('link', storyLink(ENERGY_POST))).toBeInTheDocument()
    expect(await screen.findByRole('link', storyLink(SOC_POST))).toBeInTheDocument()
    expect(screen.queryByRole('link', storyLink(GRID_POST))).toBeNull()
  })
})
