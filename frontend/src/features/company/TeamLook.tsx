import clsx from 'clsx'
import { createElement, useRef } from 'react'
import { Camera, Trash2 } from '../../components/icons'
import { Button, ErrorNote, Field } from '../../components/ui'
import type { Team } from '../../lib/company'
import { useTeamPicture } from '../../lib/companyQueries'
import { PROFILE_COLORS, PROFILE_ICONS, profileColors, swatchColor } from '../../lib/profileLook'
import { toast } from '../../lib/toast'
import { ProfileAvatar } from '../profiles/ProfileLook'

const PICTURE_TYPES = 'image/jpeg,image/png,image/webp,image/gif'
const PICTURE_MAX_BYTES = 5_000_000

type Look = Pick<Team, 'icon' | 'color' | 'picture_url'> & { name: string }

/** A team's mark: its own picture, or its icon on its colour. */
export function TeamAvatar({ team, size }: { team: Look; size: number }) {
  if (team.picture_url) {
    return (
      <img
        src={team.picture_url}
        alt=""
        width={size}
        height={size}
        className="shrink-0 rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    )
  }
  return <ProfileAvatar profile={{ ...team, spec: { name: team.name } }} size={size} />
}

type Props = {
  /** The team as saved; null while it is being made, when no picture can be stored yet. */
  team: Team | null
  name: string
  icon: string | null
  color: string | null
  onChange: (look: { icon: string | null; color: string | null }) => void
}

/** How a team looks in the list: an icon and a colour, or a picture of its own. */
export function TeamLookPicker({ team, name, icon, color, onChange }: Props) {
  const { upload, remove } = useTeamPicture()
  const input = useRef<HTMLInputElement>(null)
  const isBusy = upload.isPending || remove.isPending
  const tint = profileColors(color)

  const take = (file: File | undefined) => {
    if (!file || !team) return
    if (file.size > PICTURE_MAX_BYTES) {
      toast.error('Размер файла превышает 5 МБ. Выберите картинку поменьше.')
      return
    }
    upload.mutate(
      { teamId: team.id, file },
      { onSuccess: () => toast.success('Картинка команды обновлена') },
    )
  }

  return (
    <Field label="Вид команды" hint="значок и цвет или своя картинка" isGroup>
      <div className="space-y-3 rounded-2xl bg-surface-secondary p-3">
        <div className="flex flex-wrap items-center gap-3">
          <TeamAvatar
            team={{ name, icon, color, picture_url: team?.picture_url ?? null }}
            size={48}
          />
          {team ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                icon={<Camera size={14} />}
                isBusy={upload.isPending}
                disabled={isBusy}
                onClick={() => input.current?.click()}
              >
                {team.picture_url ? 'Заменить картинку' : 'Своя картинка'}
              </Button>
              {team.picture_url && (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Trash2 size={14} />}
                  isBusy={remove.isPending}
                  disabled={isBusy}
                  onClick={() => remove.mutate(team.id)}
                >
                  Убрать картинку
                </Button>
              )}
              <input
                ref={input}
                type="file"
                accept={PICTURE_TYPES}
                hidden
                aria-label="Файл картинки команды"
                onChange={(event) => {
                  take(event.target.files?.[0])
                  event.target.value = ''
                }}
              />
            </div>
          ) : (
            <p className="text-xs text-muted">
              Свою картинку можно загрузить после создания команды.
            </p>
          )}
        </div>
        <div role="radiogroup" aria-label="Цвет команды" className="flex flex-wrap gap-2">
          {PROFILE_COLORS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="radio"
              aria-checked={color === item.key}
              aria-label={item.label}
              onClick={() => onChange({ icon, color: item.key })}
              className={clsx(
                'size-7 rounded-full transition-transform hover:scale-110',
                color === item.key &&
                  'ring-2 ring-foreground ring-offset-2 ring-offset-surface-secondary',
              )}
              style={{ background: swatchColor(item.key) }}
            />
          ))}
        </div>
        <div role="radiogroup" aria-label="Значок команды" className="flex flex-wrap gap-1.5">
          {PROFILE_ICONS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="radio"
              aria-checked={icon === item.key}
              aria-label={item.label}
              title={item.label}
              onClick={() => onChange({ icon: item.key, color })}
              className={clsx(
                'grid size-9 place-items-center rounded-xl transition-colors',
                icon === item.key ? '' : 'text-muted hover:bg-default/60',
              )}
              style={icon === item.key ? tint : undefined}
            >
              {createElement(item.icon, { size: 18 })}
            </button>
          ))}
        </div>
        <ErrorNote error={upload.error ?? remove.error} />
      </div>
    </Field>
  )
}
