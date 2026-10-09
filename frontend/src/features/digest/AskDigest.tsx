import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { Fragment, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowUp, Info, Sparkles } from '../../components/icons'
import { EASE, INPUT_CLASS } from '../../components/tokens'
import { Card, ErrorNote, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import type { AskAnswer, Audience } from '../../lib/api'

const SUGGESTIONS: Record<Audience, string[]> = {
  specialist: [
    'Что обновить в первую очередь?',
    'Есть ли атаки на энергетику в России?',
    'Какие уязвимости уже эксплуатируют?',
  ],
  management: [
    'Какие риски для компании главные?',
    'Что нужно поручить ИБ на этой неделе?',
    'Есть ли инциденты у похожих компаний?',
  ],
}

type Exchange = { question: string; answer: AskAnswer }

/** Scrolls to an entry and makes it blink, so the eye finds what was cited. */
function showEntry(number: number) {
  const entry = document.getElementById(`entry-${number}`)
  if (!entry) return
  entry.scrollIntoView({ behavior: 'smooth', block: 'center' })
  entry.animate(
    [
      { backgroundColor: 'color-mix(in oklab, var(--accent) 16%, transparent)' },
      { backgroundColor: 'transparent' },
    ],
    { duration: 1600, easing: 'ease-out', delay: 350 },
  )
}

/** The answer's text, its "[2]" turned into buttons to the entry, word by word in. */
function AnswerText({ text }: { text: string }) {
  const parts = text.split(/(\[\d{1,3}\])/)
  let word = 0
  return (
    <p className="text-[15px] leading-relaxed text-foreground">
      {parts.map((part, index) => {
        const cite = /^\[(\d{1,3})\]$/.exec(part)
        if (cite) {
          const number = Number(cite[1])
          return (
            <button
              key={index}
              type="button"
              onClick={() => showEntry(number)}
              title={`Перейти к записи ${number}`}
              className="mx-0.5 inline-grid h-5 min-w-5 place-items-center rounded-md bg-accent-soft px-1 align-text-top text-[11px] font-semibold text-accent-soft-foreground hover:bg-accent-soft-hover"
            >
              {number}
            </button>
          )
        }
        return (
          <Fragment key={index}>
            {part.split(/(\s+)/).map((piece, at) => {
              if (/^\s+$/.test(piece) || piece === '') return piece
              word += 1
              return (
                <motion.span
                  key={at}
                  initial={{ opacity: 0, filter: 'blur(4px)' }}
                  animate={{ opacity: 1, filter: 'blur(0px)' }}
                  transition={{ duration: 0.25, delay: Math.min(word, 80) * 0.018 }}
                >
                  {piece}
                </motion.span>
              )
            })}
          </Fragment>
        )
      })}
    </p>
  )
}

function ExchangeCard({ exchange }: { exchange: Exchange }) {
  const { question, answer } = exchange
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE }}
      className="space-y-2.5"
    >
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-sm text-accent-foreground">
        {question}
      </p>
      <div
        className={clsx(
          'rounded-2xl rounded-bl-md px-4 py-3',
          answer.is_in_digest ? 'bg-surface-secondary' : 'bg-warning-soft',
        )}
      >
        {!answer.is_in_digest && (
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-warning-soft-foreground">
            <Info size={14} />В записях выпуска ответа нет
          </p>
        )}
        <AnswerText text={answer.answer} />
        {answer.citations.length > 0 && (
          <ul className="mt-2.5 space-y-1 border-t border-separator pt-2.5">
            {answer.citations.map((citation) => (
              <li key={citation.number}>
                <button
                  type="button"
                  onClick={() => showEntry(citation.number)}
                  className="flex items-start gap-2 text-left text-xs text-muted hover:text-foreground"
                >
                  <span className="mt-px grid h-4 min-w-4 place-items-center rounded bg-default px-1 text-[10px] font-semibold text-foreground">
                    {citation.number}
                  </span>
                  {citation.headline}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </motion.div>
  )
}

/**
 * Questions to the finished digest: the model answers from its entries alone
 * and points at the ones it used; a click on a number scrolls to the entry.
 */
export function AskDigest({ digestId, audience }: { digestId: string; audience: Audience }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<Exchange[]>([])
  const ask = useMutation({
    mutationFn: (text: string) => api.askDigest(digestId, text),
    onSuccess: (answer, text) => {
      setHistory((items) => [...items, { question: text, answer }].slice(-4))
      setQuestion('')
    },
  })
  const send = (text: string) => {
    const trimmed = text.trim()
    if (trimmed.length < 3 || ask.isPending) return
    ask.mutate(trimmed)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    send(question)
  }
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl bg-accent-soft text-accent">
          <Sparkles size={17} />
        </span>
        <div>
          <h2 className="text-base font-semibold">Спросить выпуск</h2>
          <p className="text-xs text-muted">
            Модель отвечает только по записям выпуска и показывает, на какие опирается
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        <AnimatePresence initial={false}>
          {history.map((exchange, index) => (
            <ExchangeCard key={`${index}-${exchange.question}`} exchange={exchange} />
          ))}
        </AnimatePresence>
        {ask.isPending && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-sm text-muted"
          >
            <Spinner className="text-accent" />
            Читаем записи выпуска
          </motion.p>
        )}
        <ErrorNote error={ask.error} />
      </div>

      {history.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS[audience].map((text) => (
            <button
              key={text}
              type="button"
              onClick={() => send(text)}
              disabled={ask.isPending}
              className="chip chip--default chip--soft px-3 py-1.5 text-[13px] transition-colors hover:bg-default-hover disabled:opacity-50"
            >
              {text}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="mt-3 flex items-center gap-2">
        <input
          className={INPUT_CLASS}
          value={question}
          maxLength={500}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Например: затронула ли уязвимость наши контроллеры Siemens?"
          aria-label="Вопрос к выпуску"
        />
        <button
          type="submit"
          disabled={question.trim().length < 3 || ask.isPending}
          aria-label="Спросить"
          className="button button--primary button--icon-only button--md shrink-0"
        >
          <ArrowUp size={18} />
        </button>
      </form>
    </Card>
  )
}
