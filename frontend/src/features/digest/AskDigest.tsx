import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowUp, ChevronDown, Info, Sparkles } from '../../components/icons'
import { EASE } from '../../components/tokens'
import { MascotLoader } from '../../components/loading'
import { ErrorNote } from '../../components/ui'
import { api } from '../../lib/api'
import { answerPieces } from '../../lib/answerText'
import { showEntry } from '../../lib/entryNav'
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

/** The answer's text, its "[2]" turned into buttons to the entry, word by word in. */
function AnswerText({ text, onOpenEntry }: { text: string; onOpenEntry: (n: number) => void }) {
  return (
    <p className="text-[15px] leading-relaxed text-foreground">
      {answerPieces(text).map((piece, index) => {
        if (piece.kind === 'gap') return piece.text
        if (piece.kind === 'cite') {
          const { number } = piece
          return (
            <button
              key={index}
              type="button"
              onClick={() => onOpenEntry(number)}
              title={`Перейти к записи ${number}`}
              className="mx-0.5 inline-grid h-5 min-w-5 place-items-center rounded-md bg-accent-soft px-1 align-text-top text-[11px] font-semibold text-accent-soft-foreground hover:bg-accent-soft-hover"
            >
              {number}
            </button>
          )
        }
        return (
          <motion.span
            key={index}
            initial={{ opacity: 0, filter: 'blur(4px)' }}
            animate={{ opacity: 1, filter: 'blur(0px)' }}
            transition={{ duration: 0.25, delay: Math.min(piece.turn, 80) * 0.018 }}
          >
            {piece.text}
          </motion.span>
        )
      })}
    </p>
  )
}

function ExchangeCard({
  exchange,
  onOpenEntry,
}: {
  exchange: Exchange
  onOpenEntry: (n: number) => void
}) {
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
        <AnswerText text={answer.answer} onOpenEntry={onOpenEntry} />
        {answer.citations.length > 0 && (
          <ul className="mt-2.5 space-y-1 border-t border-separator pt-2.5">
            {answer.citations.map((citation) => (
              <li key={citation.number}>
                <button
                  type="button"
                  onClick={() => onOpenEntry(citation.number)}
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

/** Typing "/" anywhere but in a field puts the cursor into the question. */
function useSlashToFocus(focus: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const isTyping =
        target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName ?? '')
      if (event.key !== '/' || isTyping || event.metaKey || event.ctrlKey || event.altKey) return
      event.preventDefault()
      focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [focus])
}

/**
 * Questions to the finished digest, docked at the bottom of the screen for as
 * long as the digest is on it: a reader never has to find it at the end of a
 * long issue. The model answers from the entries alone and points at the ones
 * it used; the answers open in a panel above the field, and a click on a
 * number folds the panel and scrolls to the entry.
 */
export function AskDigest({ digestId, audience }: { digestId: string; audience: Audience }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<Exchange[]>([])
  const [isOpen, setOpen] = useState(false)
  const field = useRef<HTMLInputElement>(null)
  const ask = useMutation({
    mutationFn: (text: string) => api.askDigest(digestId, text),
    onSuccess: (answer, text) => {
      setHistory((items) => [...items, { question: text, answer }].slice(-4))
      setQuestion('')
    },
  })
  const focus = useCallback(() => {
    setOpen(true)
    field.current?.focus()
  }, [])
  useSlashToFocus(focus)
  const send = (text: string) => {
    const trimmed = text.trim()
    if (trimmed.length < 3 || ask.isPending) return
    setOpen(true)
    ask.mutate(trimmed)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    send(question)
  }
  const openEntry = (number: number) => {
    setOpen(false)
    showEntry(number)
  }
  return (
    // Sticky to the bottom while the digest is in view, above the phone's bar.
    <div className="pointer-events-none sticky bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20 md:bottom-5">
      <div className="pointer-events-auto mx-auto max-w-3xl">
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.22, ease: EASE }}
              className="mb-2 overflow-hidden rounded-3xl bg-overlay shadow-overlay ring-1 ring-border"
            >
              <div className="flex items-center gap-2.5 border-b border-separator px-4 py-3">
                <span className="grid size-7 place-items-center rounded-lg bg-accent-soft text-accent">
                  <Sparkles size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">Спросить выпуск</p>
                  <p className="truncate text-xs text-muted">
                    Модель отвечает только по записям выпуска и показывает, на какие опирается
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Свернуть"
                  className="button button--ghost button--icon-only button--sm text-muted"
                >
                  <ChevronDown size={18} />
                </button>
              </div>
              <div className="max-h-[min(55vh,32rem)] space-y-4 overflow-y-auto px-4 py-4">
                {history.length === 0 && !ask.isPending && (
                  <div className="flex flex-wrap gap-1.5">
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
                <AnimatePresence initial={false}>
                  {history.map((exchange, index) => (
                    <ExchangeCard
                      key={index + '-' + exchange.question}
                      exchange={exchange}
                      onOpenEntry={openEntry}
                    />
                  ))}
                </AnimatePresence>
                {ask.isPending && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <MascotLoader label="Читаем записи выпуска" isInline />
                  </motion.div>
                )}
                <ErrorNote error={ask.error} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <form
          onSubmit={submit}
          className="flex items-center gap-2 rounded-full bg-overlay p-1.5 pl-4 shadow-overlay ring-1 ring-border"
        >
          <Sparkles size={18} className="shrink-0 text-accent" />
          <input
            ref={field}
            className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
            value={question}
            maxLength={500}
            onFocus={() => setOpen(true)}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Спросить выпуск: что обновить первым? затронуты ли наши Siemens?"
            aria-label="Вопрос к выпуску"
          />
          {!question && (
            <kbd className="hidden shrink-0 rounded-md bg-default px-1.5 py-0.5 font-mono text-xs text-muted sm:block">
              /
            </kbd>
          )}
          {history.length > 0 && !isOpen && (
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="shrink-0 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-soft-foreground"
            >
              Ответы: {history.length}
            </button>
          )}
          <button
            type="submit"
            disabled={question.trim().length < 3 || ask.isPending}
            aria-label="Спросить"
            className="button button--primary button--icon-only button--md shrink-0"
          >
            <ArrowUp size={18} />
          </button>
        </form>
      </div>
    </div>
  )
}
