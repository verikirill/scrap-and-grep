import clsx from 'clsx'
import { Camera } from '../../components/icons'
import type { AvatarPreset, Me } from '../../lib/api'
import { AVATAR_PRESETS, presetImage } from '../../lib/avatar'

type Props = {
  me: Pick<Me, 'avatar_url' | 'avatar_preset'>
  isDisabled: boolean
  onPick: (preset: AvatarPreset) => void
  onUpload: () => void
}

const TILE = clsx(
  'relative grid aspect-square w-full place-items-center rounded-full transition-[background-color,box-shadow,transform] duration-200',
  'hover:bg-surface-secondary active:scale-95 disabled:opacity-60',
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
)
const CHOSEN = 'bg-accent-soft ring-2 ring-accent'

/**
 * The reader's own photo and the nine ready pictures side by side. One is
 * chosen at a time: a ready picture replaces the photo, a new photo replaces
 * the ready picture.
 */
export function AvatarPicker({ me, isDisabled, onPick, onUpload }: Props) {
  const hasPhoto = Boolean(me.avatar_url)
  return (
    <div className="mt-4 w-full">
      <p id="avatar-picker" className="text-left text-xs font-medium text-muted">
        Картинка профиля
      </p>
      <div role="group" aria-labelledby="avatar-picker" className="mt-2 grid grid-cols-5 gap-1.5">
        <button
          type="button"
          disabled={isDisabled}
          onClick={onUpload}
          // Not a toggle: it opens the file picker. While the photo is shown,
          // none of the ready pictures is pressed.
          aria-label={hasPhoto ? 'Сменить фото' : 'Загрузить фото'}
          title={hasPhoto ? 'Своё фото' : 'Загрузить своё фото'}
          className={clsx(TILE, hasPhoto ? CHOSEN : 'border border-dashed border-border')}
        >
          {me.avatar_url ? (
            <img
              src={me.avatar_url}
              alt=""
              decoding="async"
              className="size-[86%] rounded-full object-cover"
            />
          ) : (
            <Camera size={18} className="text-muted" />
          )}
        </button>
        {AVATAR_PRESETS.map(({ key, label }) => {
          const image = presetImage(key)
          const isChosen = !hasPhoto && me.avatar_preset === key
          return (
            <button
              key={key}
              type="button"
              disabled={isDisabled}
              onClick={() => {
                if (!isChosen) onPick(key)
              }}
              aria-label={label}
              aria-pressed={isChosen}
              title={label}
              className={clsx(TILE, isChosen && CHOSEN)}
            >
              <img
                src={image.src}
                srcSet={image.srcSet}
                alt=""
                decoding="async"
                draggable={false}
                className="size-[86%] object-contain"
              />
            </button>
          )
        })}
      </div>
    </div>
  )
}
