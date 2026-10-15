import clsx from 'clsx'
import { Spinner } from '../../components/ui'
import type { AvatarPreset, SharedAccountKey } from '../../lib/api'
import { presetImage } from '../../lib/avatar'

const ACCOUNTS: readonly {
  key: SharedAccountKey
  label: string
  hint: string
  avatar: AvatarPreset
}[] = [
  {
    key: 'reader',
    label: 'Войти как читатель',
    hint: 'Все примеры профилей: ИБ АСУ ТП, ИТ-инфраструктура, цифровая трансформация',
    avatar: 'sky',
  },
  {
    key: 'analyst',
    label: 'Войти как аналитик',
    hint: 'Аналитик ИБ: защита АСУ ТП, крупные атаки и утечки',
    avatar: 'red',
  },
]

type Props = {
  /** Which account is being entered now, if any. */
  busyKey: SharedAccountKey | null
  isDisabled: boolean
  onEnter: (account: SharedAccountKey) => void
}

/**
 * One click into a ready account, no password: for a first look at the
 * service. The accounts are shared, and the note under them says so.
 */
export function SharedAccounts({ busyKey, isDisabled, onEnter }: Props) {
  return (
    <section aria-labelledby="shared-accounts" className="mt-6 border-t border-separator pt-5">
      <h2 id="shared-accounts" className="text-sm font-semibold">
        Посмотреть без регистрации
      </h2>
      <div className="mt-3 space-y-2">
        {ACCOUNTS.map((account) => {
          const image = presetImage(account.avatar)
          const isBusy = busyKey === account.key
          return (
            <button
              key={account.key}
              type="button"
              disabled={isDisabled}
              aria-busy={isBusy || undefined}
              aria-describedby={`shared-${account.key}-hint`}
              onClick={() => onEnter(account.key)}
              className={clsx(
                'group flex w-full items-center gap-3 rounded-2xl border border-separator bg-surface px-3 py-2.5 text-left',
                'transition-[background-color,border-color,transform] duration-200 hover:border-border hover:bg-surface-secondary active:scale-[0.99]',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60',
              )}
            >
              <img
                src={image.src}
                srcSet={image.srcSet}
                alt=""
                width={40}
                height={40}
                decoding="async"
                draggable={false}
                className="size-10 shrink-0 object-contain transition-transform duration-300 group-hover:-rotate-6"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{account.label}</span>
                <span id={`shared-${account.key}-hint`} className="block text-xs text-muted">
                  {account.hint}
                </span>
              </span>
              {isBusy && <Spinner className="text-muted" />}
            </button>
          )
        })}
      </div>
      <p className="mt-2 text-xs text-muted">
        Это общие аккаунты без пароля: изменения в них видят все, кто входит этими кнопками.
      </p>
    </section>
  )
}
