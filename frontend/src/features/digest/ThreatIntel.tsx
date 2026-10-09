import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Check, ChevronDown, ContentCopy, Download, Shield } from '../../components/icons'
import { DURATION, EASE, buttonClass } from '../../components/tokens'
import { AnimatedNumber } from '../../components/ui'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover'
import { api } from '../../lib/api'
import type { AttackData, ExportFormat } from '../../lib/api'
import { plural } from '../../lib/format'

/** "evil[.]example" as a machine reads it, to tell its kind. */
function refang(value: string): string {
  return value
    .replace(/\[\.\]|\(\.\)/g, '.')
    .replace('[:]', ':')
    .replace(/^hxxp/i, 'http')
}

/** What an indicator is, in the words of a defender's checklist. */
export function indicatorKind(value: string): string {
  const plain = refang(value)
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(plain)) return 'IP'
  if (/^https?:\/\//i.test(plain)) return 'URL'
  if (/^[a-f0-9]{64}$/i.test(plain)) return 'SHA-256'
  if (/^[a-f0-9]{40}$/i.test(plain)) return 'SHA-1'
  if (/^[a-f0-9]{32}$/i.test(plain)) return 'MD5'
  return 'Домен'
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [isCopied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      // No clipboard on a plain-http address: the value is on screen to select.
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={label}
      title={label}
      className="button button--ghost button--icon-only button--sm shrink-0 text-muted"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={isCopied ? 'done' : 'copy'}
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.5, opacity: 0 }}
          transition={{ duration: 0.15 }}
          className={clsx('grid place-items-center', isCopied && 'text-success')}
        >
          {isCopied ? <Check size={15} /> : <ContentCopy size={15} />}
        </motion.span>
      </AnimatePresence>
    </button>
  )
}

/**
 * What a defender can act on in an attack entry: the indicators the article
 * printed and the ATT&CK techniques it reports, folded under one line with
 * their count. Values stay defanged, so a paste into a chat opens nothing.
 */
export function IndicatorsBlock({ attack }: { attack: AttackData | null | undefined }) {
  const [isOpen, setOpen] = useState(false)
  const indicators = attack?.indicators ?? []
  const techniques = attack?.techniques ?? []
  if (indicators.length === 0 && techniques.length === 0) return null
  return (
    <div className="mt-2.5 overflow-hidden rounded-xl border border-separator">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[13px] transition-colors hover:bg-default/50"
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-danger-soft text-danger">
          <Shield size={15} />
        </span>
        <span className="min-w-0 flex-1">
          {indicators.length > 0 && (
            <span className="font-medium text-foreground">
              <AnimatedNumber value={indicators.length} />{' '}
              {plural(indicators.length, [
                'индикатор компрометации',
                'индикатора компрометации',
                'индикаторов компрометации',
              ])}
            </span>
          )}
          {indicators.length > 0 && techniques.length > 0 && (
            <span className="text-muted"> · </span>
          )}
          {techniques.length > 0 && (
            <span className="text-muted">
              {techniques.length} {plural(techniques.length, ['техника', 'техники', 'техник'])}{' '}
              ATT&CK
            </span>
          )}
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={16} className="text-muted" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: DURATION.medium, ease: EASE }}
            className="overflow-hidden border-t border-separator"
          >
            <div className="space-y-3 px-3 py-3">
              {indicators.length > 0 && (
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <p className="text-xs text-muted">Значения обезврежены: [.] вместо точки</p>
                    <CopyButton text={indicators.join('\n')} label="Скопировать все индикаторы" />
                  </div>
                  <ul className="divide-y divide-separator rounded-lg bg-surface-secondary">
                    {indicators.map((value, index) => (
                      <motion.li
                        key={value}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.2, delay: Math.min(index, 12) * 0.03 }}
                        className="flex items-center gap-2.5 py-1 pr-1 pl-2.5"
                      >
                        <span className="w-16 shrink-0 text-[11px] font-semibold tracking-wide text-muted uppercase">
                          {indicatorKind(value)}
                        </span>
                        <code className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-foreground">
                          {value}
                        </code>
                        <CopyButton text={value} label={`Скопировать ${value}`} />
                      </motion.li>
                    ))}
                  </ul>
                </div>
              )}
              {techniques.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {techniques.map((technique) => (
                    <a
                      key={technique.id}
                      href={`https://attack.mitre.org/techniques/${technique.id.replace('.', '/')}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={technique.name || technique.id}
                      className="chip chip--default chip--soft gap-1.5 px-2.5 py-1 hover:bg-default-hover"
                    >
                      <span className="font-mono font-semibold">{technique.id}</span>
                      {technique.name && <span className="text-muted">{technique.name}</span>}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const SOC_EXPORTS: { format: ExportFormat; title: string; text: string }[] = [
  {
    format: 'stix.json',
    title: 'STIX 2.1',
    text: 'Пакет для TIP, SIEM и OpenCTI: индикаторы, уязвимости и техники ATT&CK',
  },
  {
    format: 'misp.json',
    title: 'MISP',
    text: 'Событие для импорта в MISP, индикаторы помечены для обнаружения',
  },
  {
    format: 'csv',
    title: 'CSV',
    text: 'Таблица: тип, значение, обезвреженный вид, запись и ссылка',
  },
]

/** The digest's indicators for a SOC's platform, in its formats. */
export function SocExport({ digestId }: { digestId: string }) {
  const [isOpen, setOpen] = useState(false)
  return (
    <Popover open={isOpen} onOpenChange={setOpen}>
      <PopoverTrigger>
        <button type="button" className={buttonClass('secondary', 'sm')}>
          <Shield size={15} />
          Для SOC
          <ChevronDown size={14} />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-1.5">
        <p className="px-2.5 pt-1.5 pb-2 text-xs text-muted">
          Индикаторы, CVE и техники из карточек выпуска, сверенных с текстом статей
        </p>
        {SOC_EXPORTS.map((item) => (
          <a
            key={item.format}
            href={api.exportUrl(digestId, item.format)}
            download
            onClick={() => setOpen(false)}
            className="flex items-start gap-2.5 rounded-xl px-2.5 py-2 transition-colors hover:bg-default/60"
          >
            <Download size={16} className="mt-0.5 shrink-0 text-accent" />
            <span>
              <span className="block text-sm font-medium text-foreground">{item.title}</span>
              <span className="block text-xs text-muted">{item.text}</span>
            </span>
          </a>
        ))}
      </PopoverContent>
    </Popover>
  )
}
