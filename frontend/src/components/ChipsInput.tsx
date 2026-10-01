import { X } from './icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import type { KeyboardEvent } from 'react'

type Props = {
  values: string[]
  onChange: (next: string[]) => void
  placeholder: string
  label: string
  max?: number
}

/** Free-form tags: Enter or comma adds, Backspace on an empty field removes. */
export function ChipsInput({ values, onChange, placeholder, label, max = 30 }: Props) {
  const [draft, setDraft] = useState('')

  const commit = () => {
    const additions = draft
      .split(',')
      .map((part) => part.trim())
      .filter((part) => part && !values.includes(part))
    if (additions.length > 0) onChange([...values, ...additions].slice(0, max))
    setDraft('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      commit()
    } else if (event.key === 'Backspace' && draft === '' && values.length > 0) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-outline-variant bg-card px-2 py-1.5 transition-colors focus-within:border-primary hover:border-outline">
      <AnimatePresence initial={false}>
        {values.map((value) => (
          <motion.span
            key={value}
            layout
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.15 }}
            className="inline-flex items-center gap-1 rounded-md bg-surface-container py-0.5 pr-1 pl-2 text-[13px]"
          >
            {value}
            <button
              type="button"
              aria-label={`Убрать «${value}»`}
              onClick={() => onChange(values.filter((item) => item !== value))}
              className="grid size-4 place-items-center rounded text-outline hover:bg-outline-variant hover:text-foreground"
            >
              <X size={11} strokeWidth={2.5} />
            </button>
          </motion.span>
        ))}
      </AnimatePresence>
      <input
        aria-label={label}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        onBlur={commit}
        placeholder={values.length === 0 ? placeholder : ''}
        className="min-w-24 flex-1 bg-transparent py-0.5 text-sm placeholder:text-outline focus:outline-none"
      />
    </div>
  )
}
