import clsx from 'clsx'
import { useRef, useState } from 'react'
import { Camera, Trash2 } from '../../components/icons'
import { Button, ErrorNote } from '../../components/ui'
import { companyInitials } from '../../lib/company'
import { useCompanyLogo } from '../../lib/companyQueries'
import { toast } from '../../lib/toast'

const LOGO_TYPES = 'image/jpeg,image/png,image/webp,image/gif'
const LOGO_MAX_BYTES = 5_000_000
type Props = {
  name: string
  logoUrl: string | null | undefined
  size: number
  className?: string
}

/**
 * A company's mark: its logo on a white tile as wide as the logo, or its
 * initials while there is none. Decorative: the name always stands beside it.
 */
export function CompanyLogo({ name, logoUrl, size, className }: Props) {
  const [broken, setBroken] = useState<string | null>(null)
  if (logoUrl && broken !== logoUrl) {
    // As tall as the initials would be, as wide as the logo is: a wide mark
    // is not shrunk into a square.
    return (
      <span
        aria-hidden
        className={clsx('flex shrink-0 items-center rounded-2xl bg-white px-2 py-1.5', className)}
        style={{ height: size, maxWidth: size * 3.5 }}
      >
        <img
          src={logoUrl}
          alt=""
          onError={() => setBroken(logoUrl)}
          className="h-full w-auto max-w-full object-contain"
        />
      </span>
    )
  }
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-2xl bg-accent-soft font-semibold text-accent',
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
    >
      {companyInitials(name)}
    </span>
  )
}

/** The logo in the company dialog: upload one, replace it, or take it away. */
export function LogoPicker({ name, logoUrl }: { name: string; logoUrl: string | null }) {
  const { upload, remove } = useCompanyLogo()
  const input = useRef<HTMLInputElement>(null)
  const isBusy = upload.isPending || remove.isPending

  const take = (file: File | undefined) => {
    if (!file) return
    // The server checks the content; this only saves a pointless upload.
    if (file.size > LOGO_MAX_BYTES) {
      toast.error('Размер файла превышает 5 МБ. Выберите картинку поменьше.')
      return
    }
    upload.mutate(file, { onSuccess: () => toast.success('Логотип обновлён') })
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4">
        <CompanyLogo name={name} logoUrl={logoUrl} size={64} />
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            icon={<Camera size={14} />}
            isBusy={upload.isPending}
            disabled={isBusy}
            onClick={() => input.current?.click()}
          >
            {logoUrl ? 'Заменить логотип' : 'Загрузить логотип'}
          </Button>
          {logoUrl && (
            <Button
              size="sm"
              variant="ghost"
              icon={<Trash2 size={14} />}
              isBusy={remove.isPending}
              disabled={isBusy}
              onClick={() => remove.mutate(undefined, { onSuccess: () => toast('Логотип убран') })}
            >
              Убрать
            </Button>
          )}
        </div>
        <input
          ref={input}
          type="file"
          accept={LOGO_TYPES}
          hidden
          aria-label="Файл логотипа"
          onChange={(event) => {
            take(event.target.files?.[0])
            // The same file may be picked again after an error.
            event.target.value = ''
          }}
        />
      </div>
      <p className="px-1 text-xs text-muted">
        JPEG, PNG, WebP или GIF до 5 МБ. Логотип виден сотрудникам в приглашении и в аккаунте.
      </p>
      <ErrorNote error={upload.error ?? remove.error} />
    </div>
  )
}
