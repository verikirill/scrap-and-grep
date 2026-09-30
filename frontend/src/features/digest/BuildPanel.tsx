import clsx from 'clsx'
import { Sparkles } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Button, Card, ErrorNote } from '../../components/ui'
import type { Profile } from '../../lib/api'
import { plural } from '../../lib/format'
import { useCreateDigest } from '../../lib/queries'

const PERIODS = [
  { days: 1, label: 'Сутки' },
  { days: 3, label: '3 дня' },
  { days: 7, label: 'Неделя' },
  { days: 14, label: '2 недели' },
  { days: 30, label: 'Месяц' },
]

type Props = {
  profiles: Profile[]
  initialProfileId?: string | null
  onCreated: (digestId: string) => void
}

export function BuildPanel({ profiles, initialProfileId, onCreated }: Props) {
  const [profileId, setProfileId] = useState<string | null>(null)
  const [days, setDays] = useState(7)
  const create = useCreateDigest()

  // An explicit click wins; otherwise the profile from the URL, then the first one.
  const fromUrl = profiles.some((profile) => profile.id === initialProfileId)
    ? initialProfileId
    : null
  const selectedId = profileId ?? fromUrl ?? profiles[0]?.id ?? null

  const submit = () => {
    if (!selectedId) return
    // Pin the choice: after the build the URL no longer carries ?profile=.
    setProfileId(selectedId)
    create.mutate({ profileId: selectedId, days }, { onSuccess: (digest) => onCreated(digest.id) })
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold">Для кого выпуск</h2>
        <Link to="/profiles" className="text-xs text-accent-text hover:underline">
          Настроить интересы
        </Link>
      </div>
      <div
        className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3"
        role="radiogroup"
        aria-label="Профиль читателя"
      >
        {profiles.map((profile) => {
          const active = profile.id === selectedId
          const count = profile.spec.interests.length
          return (
            <button
              key={profile.id}
              type="button"
              role="radio"
              onClick={() => setProfileId(profile.id)}
              aria-checked={active}
              className={clsx(
                'relative rounded-xl border px-3.5 py-3 text-left transition-colors duration-200',
                active ? 'border-accent' : 'border-line hover:border-faint',
              )}
            >
              {active && (
                <motion.span
                  layoutId="profile-active"
                  className="absolute inset-0 rounded-[11px] bg-accent-soft"
                  transition={{ type: 'spring', stiffness: 420, damping: 36 }}
                />
              )}
              <span className="relative block truncate text-sm font-medium">
                {profile.spec.name}
              </span>
              <span className="relative mt-0.5 block text-xs text-muted">
                {count} {plural(count, ['интерес', 'интереса', 'интересов'])} · до{' '}
                {profile.spec.max_items} публикаций
              </span>
            </button>
          )
        })}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <div
          className="flex items-center gap-1 rounded-xl bg-sunken p-1"
          role="radiogroup"
          aria-label="Период"
        >
          {PERIODS.map((period) => (
            <button
              key={period.days}
              type="button"
              role="radio"
              onClick={() => setDays(period.days)}
              aria-checked={days === period.days}
              className={clsx(
                'relative rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors',
                days === period.days ? 'text-text' : 'text-muted hover:text-text',
              )}
            >
              {days === period.days && (
                <motion.span
                  layoutId="period-active"
                  className="absolute inset-0 rounded-lg bg-surface shadow-sm"
                  transition={{ type: 'spring', stiffness: 480, damping: 38 }}
                />
              )}
              <span className="relative">{period.label}</span>
            </button>
          ))}
        </div>
        <Button
          variant="primary"
          icon={<Sparkles size={16} />}
          isBusy={create.isPending}
          disabled={!selectedId}
          onClick={submit}
        >
          Собрать дайджест
        </Button>
      </div>
      {create.error && (
        <div className="mt-3">
          <ErrorNote error={create.error} />
        </div>
      )}
    </Card>
  )
}
