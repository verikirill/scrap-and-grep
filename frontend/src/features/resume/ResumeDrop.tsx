import clsx from 'clsx'
import { FileUp, ScanText } from 'lucide-react'
import { motion } from 'motion/react'
import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import type { Meta } from '../../lib/api'

// Accepted format -> extensions offered in the file dialog.
const EXTENSIONS: Record<string, string[]> = {
  pdf: ['.pdf'],
  docx: ['.docx'],
  pptx: ['.pptx'],
  odt: ['.odt'],
  txt: ['.txt'],
  md: ['.md'],
  html: ['.html', '.htm'],
  png: ['.png'],
  jpg: ['.jpg', '.jpeg'],
}

const megabytes = (bytes: number) => Math.floor(bytes / 1_000_000)

type Props = {
  meta: Meta | undefined
  isBusy: boolean
  onFile: (file: File) => void
}

/** Drop zone for a resume. Size is checked here too, to save an upload. */
export function ResumeDrop({ meta, isBusy, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [isOver, setIsOver] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  const formats = meta?.resume_formats ?? ['pdf', 'docx', 'txt', 'md']
  const limit = meta?.resume_max_bytes ?? 8_000_000
  const accept = formats.flatMap((format) => EXTENSIONS[format] ?? []).join(',')
  const hasOcr = meta?.resume_parser === 'docling'
  const formatList = formats.map((format) => format.toUpperCase()).join(', ')

  const take = (file: File | undefined) => {
    if (!file || isBusy) return
    // The server decides by the content; this only saves a pointless upload.
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!accept.split(',').includes(extension)) {
      setProblem(`Такой файл не подойдёт. Подходят: ${formatList}.`)
      return
    }
    if (file.size > limit) {
      setProblem(`Файл больше ${megabytes(limit)} МБ.`)
      return
    }
    setProblem(null)
    onFile(file)
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setIsOver(false)
    take(event.dataTransfer.files[0])
  }

  return (
    // Drag events are caught on the wrapper: a disabled button receives none,
    // and a file dropped on it would make the browser open the file instead.
    <div
      onDragOver={(event) => {
        event.preventDefault()
        if (!isBusy) setIsOver(true)
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={onDrop}
    >
      <button
        type="button"
        disabled={isBusy}
        onClick={() => input.current?.click()}
        className={clsx(
          'flex w-full flex-col items-center rounded-2xl border-2 border-dashed px-6 py-10 text-center',
          'transition-colors duration-200 disabled:pointer-events-none disabled:opacity-60',
          isOver ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-faint',
        )}
      >
        <motion.span
          animate={{ y: isOver ? -4 : 0 }}
          transition={{ type: 'spring', stiffness: 420, damping: 24 }}
          className="mb-4 grid size-12 place-items-center rounded-2xl bg-sunken text-accent-text"
        >
          <FileUp size={22} />
        </motion.span>
        <span className="text-base font-semibold">Перетащите резюме сюда</span>
        <span className="mt-1 text-sm text-muted">или нажмите, чтобы выбрать файл</span>
        <span className="mt-4 text-xs text-faint">
          {formatList} · до {megabytes(limit)} МБ
        </span>
        {hasOcr && (
          <span className="mt-2 inline-flex items-center gap-1.5 text-xs text-faint">
            <ScanText size={13} />
            Сканы и фотографии страниц читаются распознаванием текста
          </span>
        )}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        // Opened by the button above; kept out of the page and of the tab order.
        hidden
        onChange={(event) => {
          take(event.target.files?.[0])
          // The same file may be picked again after an error.
          event.target.value = ''
        }}
      />
      {problem && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {problem}
        </p>
      )}
    </div>
  )
}
