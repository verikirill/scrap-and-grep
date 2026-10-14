import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { AskAnswer } from '../../lib/api'
import { makeAskAnswer } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { AskDigest } from './AskDigest'

const askUrl = apiUrl('/digests/digest-1/ask')

/** The server answering questions about digest-1; returns what it was asked, in order. */
function serveAnswers(answer: (question: string) => AskAnswer = () => makeAskAnswer()) {
  const questions: string[] = []
  server.use(
    http.post(askUrl, async ({ request }) => {
      const { question } = (await request.json()) as { question: string }
      questions.push(question)
      return HttpResponse.json(answer(question))
    }),
  )
  return questions
}

/** The answer's paragraph, its words and citation numbers read as one text. */
function findAnswer(text: string) {
  return screen.findByText((_, element) => element?.tagName === 'P' && element.textContent === text)
}

/** An entry of the issue as DigestView draws it, with the jump to it observed. */
function entryStub(number: number) {
  const entry = document.createElement('article')
  entry.id = `entry-${number}`
  const scrollIntoView = vi.fn()
  // jsdom has no Web Animations: the blink of the entry is a stub here.
  Object.assign(entry, { scrollIntoView, animate: vi.fn() })
  document.body.append(entry)
  return { scrollIntoView, remove: () => entry.remove() }
}

const field = () => screen.getByRole('textbox', { name: 'Вопрос к выпуску' })
const askButton = () => screen.getByRole('button', { name: 'Спросить' })

describe('AskDigest', () => {
  it('offers a specialist’s questions once the field is focused and asks the one chosen', async () => {
    const questions = serveAnswers()
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)
    expect(screen.queryByText('Спросить выпуск')).toBeNull()

    await user.click(field())

    expect(screen.getByText('Спросить выпуск')).toBeInTheDocument()
    for (const question of [
      'Что обновить в первую очередь?',
      'Есть ли атаки на энергетику в России?',
      'Какие уязвимости уже эксплуатируют?',
    ]) {
      expect(screen.getByRole('button', { name: question })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Какие риски для компании главные?' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Какие уязвимости уже эксплуатируют?' }))

    // "[1]" and "[2]" stand in the text as the numbers of the entries.
    expect(
      await findAnswer(
        'Да, две записи. Уязвимость контроллеров SIMATIC S7-1500 уже используется в атаках 1, а подрядчикам сетевых компаний приходят фишинговые письма от имени Минэнерго 2.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Какие уязвимости уже эксплуатируют?')).toBeInTheDocument()
    expect(questions).toEqual(['Какие уязвимости уже эксплуатируют?'])
    // Asked once, the panel holds the answers instead of the offers.
    expect(screen.queryByRole('button', { name: 'Что обновить в первую очередь?' })).toBeNull()
  })

  it('offers management questions about the company', async () => {
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="management" />)

    await user.click(field())

    for (const question of [
      'Какие риски для компании главные?',
      'Что нужно поручить ИБ на этой неделе?',
      'Есть ли инциденты у похожих компаний?',
    ]) {
      expect(screen.getByRole('button', { name: question })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Что обновить в первую очередь?' })).toBeNull()
  })

  it('asks a typed question of three characters or more, trimmed, and clears the field', async () => {
    const questions = serveAnswers()
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)
    expect(askButton()).toBeDisabled()

    await user.type(field(), '  ок ')
    expect(askButton()).toBeDisabled()
    // Two characters are not a question: Enter sends nothing.
    await user.keyboard('{Enter}')

    await user.clear(field())
    await user.type(field(), ' что ')
    expect(askButton()).toBeEnabled()
    await user.click(askButton())

    expect(await screen.findByText('что')).toBeInTheDocument()
    expect(questions).toEqual(['что'])
    await waitFor(() => expect(field()).toHaveValue(''))
  })

  it('jumps from a number in the answer or under it to the entry and folds the panel', async () => {
    serveAnswers()
    const first = entryStub(1)
    const second = entryStub(2)
    try {
      const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)
      await user.type(field(), 'Что с Минэнерго?{Enter}')
      const answer = await findAnswer(
        'Да, две записи. Уязвимость контроллеров SIMATIC S7-1500 уже используется в атаках 1, а подрядчикам сетевых компаний приходят фишинговые письма от имени Минэнерго 2.',
      )

      await user.click(within(answer).getByRole('button', { name: '2' }))

      await waitFor(() => expect(screen.queryByText('Спросить выпуск')).toBeNull())
      expect(second.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
      expect(first.scrollIntoView).not.toHaveBeenCalled()

      // The folded answers wait behind a count; the list under the answer jumps too.
      await user.click(screen.getByRole('button', { name: 'Ответы: 1' }))
      await user.click(
        await screen.findByRole('button', {
          name: /Уязвимость SIMATIC S7-1500 используется в атаках$/,
        }),
      )

      await waitFor(() => expect(screen.queryByText('Спросить выпуск')).toBeNull())
      expect(first.scrollIntoView).toHaveBeenCalledTimes(1)
    } finally {
      first.remove()
      second.remove()
    }
  })

  it('warns when the entries of the issue do not hold the answer', async () => {
    serveAnswers(() =>
      makeAskAnswer({
        answer: 'Записей о программах-вымогателях в выпуске нет.',
        citations: [],
        is_in_digest: false,
      }),
    )
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)

    await user.type(field(), 'Были ли атаки шифровальщиков?{Enter}')

    expect(await findAnswer('Записей о программах-вымогателях в выпуске нет.')).toBeInTheDocument()
    expect(screen.getByText('В записях выпуска ответа нет')).toBeInTheDocument()
  })

  it('keeps the last four answers and counts them once folded', async () => {
    serveAnswers((question) => makeAskAnswer({ answer: `Ответ: ${question}`, citations: [] }))
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)

    for (const number of [1, 2, 3, 4, 5]) {
      await user.type(field(), `Вопрос номер ${number}{Enter}`)
      expect(await screen.findByText(`Вопрос номер ${number}`)).toBeInTheDocument()
      await waitFor(() => expect(field()).toHaveValue(''))
    }

    expect(screen.queryByText('Вопрос номер 1')).toBeNull()
    for (const number of [2, 3, 4, 5]) {
      expect(screen.getByText(`Вопрос номер ${number}`)).toBeInTheDocument()
    }

    await user.click(screen.getByRole('button', { name: 'Свернуть' }))

    expect(await screen.findByRole('button', { name: 'Ответы: 4' })).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Вопрос номер 5')).toBeNull())
  })

  it('takes "/" typed outside a field as a call to ask, and leaves other keys alone', async () => {
    const { user } = renderWithProviders(
      <>
        <input aria-label="Заметка" />
        <AskDigest digestId="digest-1" audience="specialist" />
      </>,
    )

    // With a modifier it is the browser's shortcut, not the app's.
    await user.keyboard('{Control>}/{/Control}')
    expect(field()).not.toHaveFocus()

    await user.keyboard('/')

    expect(field()).toHaveFocus()
    expect(field()).toHaveValue('')
    expect(screen.getByText('Спросить выпуск')).toBeInTheDocument()

    // In another field "/" is just a character.
    const note = screen.getByRole('textbox', { name: 'Заметка' })
    await user.click(note)
    await user.keyboard('/')
    expect(note).toHaveFocus()
    expect(note).toHaveValue('/')
  })

  it('shows the server’s refusal and keeps the question for another try', async () => {
    const questions = serveAnswers()
    server.use(
      http.post(
        askUrl,
        () => HttpResponse.json({ detail: 'Модель не ответила вовремя' }, { status: 504 }),
        { once: true },
      ),
    )
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)

    await user.type(field(), 'Что обновить первым?{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('Модель не ответила вовремя')
    expect(field()).toHaveValue('Что обновить первым?')

    await user.click(askButton())

    expect(await screen.findByText('Что обновить первым?')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
    expect(questions).toEqual(['Что обновить первым?'])
  })

  it('asks one question at a time and says it is reading meanwhile', async () => {
    let release = () => {}
    const answered = new Promise<void>((resolve) => {
      release = resolve
    })
    const questions: string[] = []
    server.use(
      http.post(askUrl, async ({ request }) => {
        questions.push(((await request.json()) as { question: string }).question)
        await answered
        return HttpResponse.json(makeAskAnswer({ answer: 'Обновите прошивку.', citations: [] }))
      }),
    )
    const { user } = renderWithProviders(<AskDigest digestId="digest-1" audience="specialist" />)

    await user.type(field(), 'Что обновить первым?{Enter}')

    expect(await screen.findByText('Читаем записи выпуска')).toBeInTheDocument()
    expect(askButton()).toBeDisabled()
    await user.keyboard('{Enter}')
    release()

    expect(await findAnswer('Обновите прошивку.')).toBeInTheDocument()
    expect(screen.queryByText('Читаем записи выпуска')).toBeNull()
    expect(questions).toEqual(['Что обновить первым?'])
  })
})
