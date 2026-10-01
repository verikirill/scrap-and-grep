import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { LogoMark } from '../../components/Logo'

// The product in one picture: news run past like `tail -f`, and the words a
// reader cares about light up like `grep` matches.
const HEADLINES = [
  {
    source: 'SecurityWeek',
    text: 'Siemens закрыла уязвимость в SIMATIC S7-1500',
    match: 'SIMATIC',
  },
  { source: 'Хабр', text: 'Как мы перевели SCADA на отечественную ОС', match: 'SCADA' },
  {
    source: 'CISA',
    text: 'CVE-2026-20411: удалённое выполнение кода в шлюзе',
    match: 'CVE-2026-20411',
  },
  { source: 'CNews', text: 'ФСТЭК обновила требования к объектам КИИ', match: 'КИИ' },
  {
    source: 'Dark Reading',
    text: 'Шифровальщик остановил диспетчерскую энергосети',
    match: 'энергосети',
  },
  {
    source: 'Industrial Cyber',
    text: 'МЭК 61850: новые профили защиты подстанций',
    match: 'МЭК 61850',
  },
]
const SHOWN = 4
const STEP_MS = 2200

function Line({ text, match }: { text: string; match: string }) {
  const at = text.indexOf(match)
  if (at < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded-[5px] bg-[#7d9bff]/25 px-1 text-[#b7c4ff]">{match}</mark>
      {text.slice(at + match.length)}
    </>
  )
}

/**
 * The sign-in picture: the mark above a terminal where headlines stream in.
 * Decorative, so hidden from assistive technology. Only opacity and position
 * move; with "reduce motion" on the list stands still.
 */
export function TailVisual() {
  const isStill = useReducedMotion()
  const [head, setHead] = useState(0)

  useEffect(() => {
    if (isStill) return
    const timer = window.setInterval(() => setHead((value) => value + 1), STEP_MS)
    return () => window.clearInterval(timer)
  }, [isStill])

  const lines = Array.from({ length: SHOWN }, (_, index) => {
    const at = head + index
    return { key: at, ...HEADLINES[at % HEADLINES.length] }
  })

  return (
    <div aria-hidden className="flex w-full max-w-[460px] flex-col items-center gap-8">
      <LogoMark size={112} className="shadow-[0_24px_80px_rgba(125,155,255,0.25)]" />
      <div className="w-full overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] font-mono text-[13px] leading-6 shadow-2xl backdrop-blur">
        <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
        </div>
        <div className="px-4 pt-3 text-white/45">
          $ tail -f news | grep -iE &quot;scada|cve|кии|мэк&quot;
        </div>
        <ul className="relative h-[176px] px-4 pt-2 pb-4">
          <AnimatePresence initial={false} mode="popLayout">
            {lines.map((line) => (
              <motion.li
                key={line.key}
                layout="position"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ type: 'spring', stiffness: 260, damping: 30 }}
                className="truncate py-1 text-white/80"
              >
                <span className="text-white/35">{line.source} › </span>
                <Line text={line.text} match={line.match} />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  )
}
