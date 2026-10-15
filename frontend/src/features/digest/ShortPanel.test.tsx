import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Meta, Video } from '../../lib/api'
import { makeMeta, makeVideo, makeVoiceOptions } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ShortPanel } from './ShortPanel'

const shortUrl = apiUrl('/digests/digest-1/short')

/** A server that renders videos, with or without voices; the video as it keeps it. */
function serveShorts(video: Video | null, meta: Partial<Meta> = {}) {
  let current = video
  const ordered: (string | null)[] = []
  server.use(
    http.get(apiUrl('/meta'), () =>
      HttpResponse.json(
        makeMeta({ shorts: true, shorts_voice: true, short_voices: makeVoiceOptions(), ...meta }),
      ),
    ),
    http.get(shortUrl, () => HttpResponse.json(current)),
    http.post(shortUrl, async ({ request }) => {
      const { voice } = (await request.json()) as { voice: string | null }
      ordered.push(voice)
      current = makeVideo({
        status: 'queued',
        stage: null,
        progress: 0,
        url: null,
        requested_voice: voice,
      })
      return HttpResponse.json(current)
    }),
  )
  return {
    ordered,
    finish: (next: Video) => {
      current = next
    },
  }
}

describe('ShortPanel', () => {
  it('is not offered on a server that cannot render videos', async () => {
    let asked = 0
    server.use(
      http.get(apiUrl('/meta'), () => {
        asked += 1
        return HttpResponse.json(makeMeta({ shorts: false }))
      }),
    )
    // No handler for the video: asking for it would fail the test.
    renderWithProviders(<ShortPanel digestId="digest-1" />)
    await waitFor(() => expect(asked).toBe(1))
    expect(screen.queryByRole('heading', { name: 'Короткое видео' })).toBeNull()
  })

  it('orders a video in the voice picked and follows it step by step until it plays', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const service = serveShorts(null)
    const { user } = renderWithProviders(<ShortPanel digestId="digest-1" />, {
      userOptions: { advanceTimers: vi.advanceTimersByTime },
    })
    const voices = await screen.findByRole('group', { name: 'Голос' })
    expect(within(voices).getByRole('radio', { name: 'Ведущий' })).toBeChecked()

    await user.click(within(voices).getByRole('radio', { name: 'Ведущая' }))
    await user.click(screen.getByRole('button', { name: 'Создать видео' }))

    expect(await screen.findByRole('progressbar', { name: 'Готовность видео' })).toHaveAttribute(
      'aria-valuetext',
      'В очереди',
    )
    expect(service.ordered).toEqual(['presenter'])
    // While it is being made there is nothing to order.
    expect(screen.queryByRole('button', { name: /видео|заново/ })).toBeNull()

    service.finish(makeVideo({ status: 'running', stage: 'voice', progress: 0.5, url: null }))
    await vi.advanceTimersByTimeAsync(2_500)
    await waitFor(() =>
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50'),
    )
    expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Озвучка')
    expect(screen.getByText('(готово)').closest('li')).toHaveTextContent('Сценарий')

    service.finish(makeVideo({ requested_voice: 'presenter', voice: 'qwen3-tts:presenter' }))
    await vi.advanceTimersByTimeAsync(2_500)
    expect(
      await screen.findByLabelText('Короткое видео по выпуску, субтитры встроены в кадр'),
    ).toHaveAttribute('src', '/api/v1/digests/digest-1/short.mp4?v=1791968850')
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('plays a ready video with what it is made of and offers a new cut', async () => {
    const { ordered } = serveShorts(makeVideo({ by_model: false }))
    const { user } = renderWithProviders(<ShortPanel digestId="digest-1" />)

    expect(
      await screen.findByText('0:58 · голос «Ведущий» · сценарий из выжимок · 6,8 МБ'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Скачать MP4' })).toHaveAttribute(
      'href',
      '/api/v1/digests/digest-1/short.mp4?v=1791968850&download=1',
    )

    await user.click(screen.getByRole('button', { name: 'Смонтировать заново' }))

    expect(await screen.findByRole('progressbar')).toBeInTheDocument()
    // The last video's voice stays picked.
    expect(ordered).toEqual(['anchor'])
  })

  it('names the voice service as the engine and the voice by its title', async () => {
    serveShorts(makeVideo({ voice: 'qwen3-tts:anchor' }), { voice_engine: 'qwen3-tts' })
    renderWithProviders(<ShortPanel digestId="digest-1" />)

    expect(await screen.findByText('Озвучка Qwen3-TTS')).toBeInTheDocument()
    expect(await screen.findByText(/голос «Ведущий»/)).toBeInTheDocument()
  })

  it('names Yandex SpeechKit and its voice when SpeechKit speaks', async () => {
    const yandex = [
      { id: 'alena', title: 'Алёна', default: true },
      { id: 'zahar', title: 'Захар', default: false },
    ]
    serveShorts(makeVideo({ voice: 'yandex:zahar', requested_voice: 'zahar' }), {
      voice_engine: 'yandex',
      short_voices: yandex,
    })
    renderWithProviders(<ShortPanel digestId="digest-1" />)

    expect(await screen.findByText('Озвучка Yandex SpeechKit')).toBeInTheDocument()
    expect(await screen.findByText(/голос «Захар»/)).toBeInTheDocument()
    expect(screen.queryByText(/Qwen3-TTS/)).toBeNull()
    expect(screen.getByRole('radio', { name: 'Захар' })).toBeChecked()
  })

  it('names the engine of a voice the list no longer has', async () => {
    serveShorts(makeVideo({ voice: 'yandex:ermil' }), { voice_engine: 'yandex', short_voices: [] })
    renderWithProviders(<ShortPanel digestId="digest-1" />)

    expect(await screen.findByText(/голос Yandex SpeechKit ermil/)).toBeInTheDocument()
  })

  it('makes a video with subtitles only on a server without voices', async () => {
    const { ordered } = serveShorts(null, { shorts_voice: false, short_voices: [] })
    const { user } = renderWithProviders(<ShortPanel digestId="digest-1" />)

    expect(
      await screen.findByText(
        'Озвучка на этом сервере не подключена, в видео будут только субтитры',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Голос' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Создать видео' }))
    expect(await screen.findByRole('progressbar')).toBeInTheDocument()
    expect(ordered).toEqual([null])
  })

  it('says why the video failed, and why an order was refused', async () => {
    serveShorts(makeVideo({ status: 'failed', error: 'Монтаж прерван', url: null }))
    server.use(
      http.post(shortUrl, () =>
        HttpResponse.json({ detail: 'Другое видео уже монтируется' }, { status: 409 }),
      ),
    )
    const { user } = renderWithProviders(<ShortPanel digestId="digest-1" />)
    expect(await screen.findByText('Монтаж прерван')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Смонтировать заново' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Другое видео уже монтируется')
    expect(screen.getByText('Монтаж прерван')).toBeInTheDocument()
  })
})
