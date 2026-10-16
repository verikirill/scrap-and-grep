import { AnimatePresence, motion } from 'motion/react'
import { Moon, Sun } from './icons'
import { DURATION, EASE } from './tokens'

/** The switch between the light and the dark theme: a sun or a moon that turns over. */
export function ThemeButton({ dark, onToggle }: { dark: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      // The icon and the name both say where a press leads, not where one is.
      aria-label={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      title={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      className="button button--ghost button--icon-only button--md shrink-0 text-muted"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={dark ? 'sun' : 'moon'}
          initial={{ rotate: -90, scale: 0.6, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.6, opacity: 0 }}
          transition={{ duration: DURATION.short, ease: EASE }}
        >
          {dark ? <Sun size={19} /> : <Moon size={19} />}
        </motion.span>
      </AnimatePresence>
    </button>
  )
}
