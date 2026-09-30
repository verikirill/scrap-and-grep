import clsx from 'clsx'
import { Plus, RotateCcw, Save, Sparkles, Trash2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { Button, ErrorNote, PageHeader } from '../components/ui'
import { PreviewPanel } from '../features/profiles/PreviewPanel'
import { ProfileForm } from '../features/profiles/ProfileForm'
import type { Profile, ProfileSpec } from '../lib/api'
import { useDeleteProfile, useProfiles, useSaveProfile } from '../lib/queries'

const NEW = 'new'

const BLANK: ProfileSpec = {
  name: 'Новый профиль',
  role: '',
  interests: [{ id: 'interest-1', title: '', description: '', keywords: [], weight: 1 }],
  exclusions: [],
  min_score: 0.5,
  max_items: 20,
  languages: ['ru', 'en'],
  categories: [],
}

/** What the API would reject; shown next to the save button instead of a 422. */
function problems(spec: ProfileSpec): string | null {
  if (spec.name.trim().length < 2) return 'Дайте профилю название.'
  if (spec.interests.some((interest) => interest.title.trim().length < 2)) {
    return 'У каждого интереса должно быть название.'
  }
  return null
}

type EditorProps = {
  profiles: Profile[]
  stored: Profile | null
  onSelect: (id: string | null) => void
}

/**
 * Holds the draft of one profile. The parent remounts it (via `key`) only when
 * another profile is picked. A save keeps the editor mounted, so an open
 * section, the focus and anything typed while the request was in flight stay.
 */
function ProfileEditor({ profiles, stored, onSelect }: EditorProps) {
  const navigate = useNavigate()
  const save = useSaveProfile()
  const remove = useDeleteProfile()
  const saved = stored?.spec ?? null
  const [draft, setDraft] = useState<ProfileSpec>(saved ?? BLANK)

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved])
  const problem = problems(draft)
  const activeId = stored?.id ?? NEW

  const persist = (then?: (id: string) => void) => {
    if (problem) return
    save.mutate(
      { id: stored?.id ?? null, spec: draft },
      {
        onSuccess: (profile) => {
          onSelect(profile.id)
          then?.(profile.id)
        },
      },
    )
  }

  /** Switching away from unsaved edits asks first instead of dropping them. */
  const leaveTo = (id: string | null) => {
    if (dirty && !window.confirm('Несохранённые правки пропадут. Перейти?')) return
    onSelect(id)
  }

  return (
    <>
      <PageHeader
        title="Интересы"
        subtitle="Профиль описывает читателя: что ему важно, что не показывать и насколько строго отбирать. Справа видно, как каждая правка меняет подборку."
        actions={
          <>
            {dirty && saved && (
              <Button
                variant="ghost"
                icon={<RotateCcw size={15} />}
                onClick={() => setDraft(saved)}
              >
                Отменить правки
              </Button>
            )}
            <Button
              icon={<Save size={15} />}
              disabled={!dirty || Boolean(problem)}
              isBusy={save.isPending}
              onClick={() => persist()}
            >
              Сохранить
            </Button>
            <Button
              variant="primary"
              icon={<Sparkles size={15} />}
              disabled={Boolean(problem) || save.isPending}
              onClick={() =>
                dirty || !stored
                  ? persist((id) => navigate(`/?profile=${id}`))
                  : navigate(`/?profile=${stored.id}`)
              }
            >
              {dirty ? 'Сохранить и собрать' : 'Собрать дайджест'}
            </Button>
          </>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-1.5">
        {profiles.map((profile) => (
          <button
            key={profile.id}
            type="button"
            onClick={() => leaveTo(profile.id)}
            aria-current={profile.id === activeId ? 'true' : undefined}
            className={clsx(
              'relative rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              profile.id === activeId ? 'text-accent-text' : 'text-muted hover:text-text',
            )}
          >
            {profile.id === activeId && (
              <motion.span
                layoutId="profile-tab"
                className="absolute inset-0 rounded-lg bg-accent-soft"
                transition={{ type: 'spring', stiffness: 480, damping: 38 }}
              />
            )}
            <span className="relative">{profile.spec.name}</span>
          </button>
        ))}
        <Button
          size="sm"
          variant="ghost"
          icon={<Plus size={15} />}
          onClick={() => leaveTo(NEW)}
          disabled={activeId === NEW}
        >
          Новый
        </Button>
        {stored && profiles.length > 1 && (
          <Button
            size="sm"
            variant="danger"
            className="ml-auto"
            icon={<Trash2 size={14} />}
            isBusy={remove.isPending}
            onClick={() => {
              if (window.confirm(`Удалить профиль «${stored.spec.name}»?`)) {
                remove.mutate(stored.id, { onSuccess: () => onSelect(null) })
              }
            }}
          >
            Удалить профиль
          </Button>
        )}
      </div>

      <div className="mb-4 space-y-2">
        <ErrorNote error={save.error ?? remove.error} />
        {dirty && problem && <p className="text-sm text-spark">{problem}</p>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <ProfileForm spec={draft} onChange={setDraft} />
        <div className="lg:sticky lg:top-9 lg:self-start">
          <PreviewPanel draft={draft} saved={saved} isDirty={dirty} />
        </div>
      </div>
    </>
  )
}

export function ProfilesPage() {
  const profiles = useProfiles()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (!profiles.data) {
    return (
      <>
        <PageHeader title="Интересы" />
        <ErrorNote error={profiles.error} />
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="skeleton h-96" />
          <div className="skeleton h-96" />
        </div>
      </>
    )
  }

  const activeId = selectedId ?? profiles.data[0]?.id ?? NEW
  const stored = profiles.data.find((profile) => profile.id === activeId) ?? null
  return (
    <ProfileEditor
      key={stored?.id ?? NEW}
      profiles={profiles.data}
      stored={stored}
      onSelect={setSelectedId}
    />
  )
}
