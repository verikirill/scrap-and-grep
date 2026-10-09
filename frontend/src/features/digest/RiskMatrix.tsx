import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { ArrowRight } from '../../components/icons'
import { EASE } from '../../components/tokens'
import { Card } from '../../components/ui'
import { showEntry } from '../../lib/entryNav'
import { plural } from '../../lib/format'
import { riskCells } from '../../lib/risk'
import type { Placed } from '../../lib/risk'

const SEVERITY = ['Умеренная', 'Высокая', 'Критическая']
const EXPOSURE = ['Прочее в выпуске', 'По интересам профиля', 'Наши системы']
const SEVERITY_HINT =
  'Критическая: эксплуатируется (CISA KEV, БДУ) или CVSS от 9. Высокая: публичный эксплойт или CVSS от 7.'
const EXPOSURE_HINT =
  'Наши системы: запись называет продукт из профиля. По интересам: релевантность от 0,8.'

// The tone of a cell grows with the sum of its two bands, 0 to 4.
const CELL_TONES = [
  'bg-success-soft',
  'bg-success-soft',
  'bg-warning-soft',
  'bg-danger-soft',
  'bg-danger',
] as const

/**
 * The issue's vulnerabilities on two axes, as a 3×3 heat map: how dangerous
 * the flaw is and how close it is to the reader. The top right corner is what
 * to patch first; a number opens its entry.
 */
export function RiskMatrix({ entries }: { entries: Placed[] }) {
  const cells = riskCells(entries)
  const count = cells.flat(2).length
  // The entry under the pointer, named at once below the grid: a native
  // title waits a second and a half, too long to learn the numbers open entries.
  const [hovered, setHovered] = useState<Placed | null>(null)
  if (count === 0) return null
  let order = 0
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">Матрица риска</h2>
        <p className="text-xs text-muted">
          {count} {plural(count, ['уязвимость', 'уязвимости', 'уязвимостей'])} · правый верхний угол
          обновлять первым
        </p>
      </div>
      <div className="mt-4 grid grid-cols-[auto_repeat(3,minmax(0,1fr))] gap-1.5">
        {[2, 1, 0].map((exposure) => (
          <div key={exposure} className="contents">
            <div
              className="flex items-center justify-end pr-2 text-right text-[11px] leading-tight text-muted sm:text-xs"
              title={EXPOSURE_HINT}
            >
              {EXPOSURE[exposure]}
            </div>
            {[0, 1, 2].map((severity) => {
              const placed = cells[exposure][severity]
              const tone = CELL_TONES[exposure + severity]
              return (
                <motion.div
                  key={severity}
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    duration: 0.35,
                    ease: EASE,
                    delay: (2 - exposure + severity) * 0.05,
                  }}
                  className={clsx(
                    'flex min-h-16 flex-wrap content-center items-center justify-center gap-1.5 rounded-xl p-2',
                    tone,
                  )}
                >
                  {placed.map(({ position, item }) => {
                    order += 1
                    return (
                      <motion.button
                        key={position}
                        type="button"
                        onClick={() => showEntry(position)}
                        onPointerEnter={() => setHovered({ position, item })}
                        onPointerLeave={() => setHovered(null)}
                        onFocus={() => setHovered({ position, item })}
                        onBlur={() => setHovered(null)}
                        aria-label={`Открыть запись ${position}: ${item.headline}`}
                        initial={{ scale: 0 }}
                        animate={{
                          scale: 1,
                          // One soft pulse after they land: these are things to press.
                          boxShadow: [
                            '0 0 0 0px rgb(0 111 238 / 0)',
                            '0 0 0 6px rgb(0 111 238 / 0.35)',
                            '0 0 0 0px rgb(0 111 238 / 0)',
                          ],
                        }}
                        whileHover={{ scale: 1.18 }}
                        whileTap={{ scale: 0.92 }}
                        transition={{
                          scale: {
                            type: 'spring',
                            stiffness: 500,
                            damping: 22,
                            delay: 0.25 + order * 0.04,
                          },
                          boxShadow: { duration: 0.9, delay: 0.7 + order * 0.04 },
                        }}
                        className={clsx(
                          'grid size-7 place-items-center rounded-full text-xs font-semibold ring-1 transition-colors',
                          'hover:bg-accent hover:text-accent-foreground hover:ring-accent',
                          exposure + severity === 4
                            ? 'bg-white text-danger ring-white'
                            : 'bg-surface text-foreground ring-border',
                        )}
                      >
                        {position}
                      </motion.button>
                    )
                  })}
                </motion.div>
              )
            })}
          </div>
        ))}
        <div />
        {SEVERITY.map((label) => (
          <div
            key={label}
            className="pt-1 text-center text-[11px] text-muted sm:text-xs"
            title={SEVERITY_HINT}
          >
            {label}
          </div>
        ))}
      </div>
      <div className="mt-3 flex min-h-9 items-center rounded-xl bg-surface-secondary px-3 text-[13px]">
        <AnimatePresence mode="wait" initial={false}>
          {hovered ? (
            <motion.span
              key={hovered.position}
              initial={{ opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="flex min-w-0 items-center gap-2"
            >
              <span className="grid h-5 min-w-5 shrink-0 place-items-center rounded-md bg-accent px-1 text-[11px] font-semibold text-accent-foreground">
                {hovered.position}
              </span>
              <span className="truncate font-medium text-foreground">{hovered.item.headline}</span>
              <ArrowRight size={14} className="shrink-0 text-accent" />
            </motion.span>
          ) : (
            <motion.span
              key="hint"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="text-muted"
            >
              Номер в клетке - запись выпуска: наведите, чтобы увидеть заголовок, нажмите, чтобы
              перейти
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <p className="mt-3 text-xs text-muted">
        По вертикали близость к вам, по горизонтали опасность уязвимости. {SEVERITY_HINT}{' '}
        {EXPOSURE_HINT}
      </p>
    </Card>
  )
}
