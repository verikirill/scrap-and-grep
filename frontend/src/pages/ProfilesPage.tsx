import clsx from 'clsx'
import { Newspaper, Plus, RotateCcw, Save, Trash2 } from '../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { EASE } from '../components/tokens'
import { Button, ErrorNote, PageHeader } from '../components/ui'
import { AdaptationPanel } from '../features/profiles/AdaptationPanel'
import { PreviewPanel } from '../features/profiles/PreviewPanel'
import { ProfileForm } from '../features/profiles/ProfileForm'
import { ProfileAvatar, ProfileLookPicker } from '../features/profiles/ProfileLook'
import { ShareProfileButton } from '../features/profiles/ShareProfile'
import type { Profile, ProfileSpec } from '../lib/api'
import { useDeleteProfile, useProfiles, useSaveProfile } from '../lib/queries'
import { useConfirmLeave } from '../lib/useConfirmLeave'

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
  audience: 'specialist',
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
  useConfirmLeave(dirty, 'Несохранённые правки пропадут. Уйти со страницы?')

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

  /**
   * An accepted suggestion is already saved as a new version. The draft takes
   * the same change, so edits in progress stay and nothing looks unsaved.
   */
  const applySuggestion = (profile: Profile) => {
    // The version the suggestion was accepted on.
    const before = saved
    setDraft((current) => {
      if (!before || JSON.stringify(current) === JSON.stringify(before)) return profile.spec
      const knownIds = new Set([...before.interests, ...current.interests].map((item) => item.id))
      const known = new Set([...before.exclusions, ...current.exclusions])
      return {
        ...current,
        interests: [
          ...current.interests,
          ...profile.spec.interests.filter((item) => !knownIds.has(item.id)),
        ],
        exclusions: [
          ...current.exclusions,
          ...profile.spec.exclusions.filter((item) => !known.has(item)),
        ],
      }
    })
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
        subtitle="Профиль задаёт критерии отбора: важные темы, исключения и строгость фильтрации. Предпросмотр сразу показывает, как правки влияют на выпуск."
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
              icon={<Newspaper size={15} />}
              disabled={Boolean(problem) || save.isPending}
              onClick={() =>
                dirty || !stored
                  ? persist((id) => navigate(`/?profile=${id}`))
                  : navigate(`/?profile=${stored.id}`)
              }
            >
              {dirty ? 'Сохранить и собрать' : 'Собрать выпуск'}
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
              // Never wider than the row: a long name used to push the whole page sideways on a phone.
              'relative isolate flex max-w-full min-w-0 items-center gap-2 rounded-full py-1 pr-3.5 pl-1 text-sm font-medium transition-colors duration-300',
              profile.id === activeId
                ? 'text-primary-foreground'
                : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface',
            )}
          >
            {profile.id === activeId && (
              <motion.span
                layoutId="profile-tab"
                className="absolute inset-0 -z-10 rounded-full bg-primary shadow-elevation-1"
                transition={{ type: 'spring', stiffness: 420, damping: 32 }}
              />
            )}
            <ProfileAvatar profile={profile} size={28} />
            <span className="relative min-w-0 truncate sm:max-w-80" title={profile.spec.name}>
              {profile.spec.name}
            </span>
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
        {stored && (
          <div className="ml-auto flex flex-wrap gap-1.5">
            <ShareProfileButton profile={stored} />
            {profiles.length > 1 && (
              <Button
                size="sm"
                variant="danger"
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
        )}
      </div>

      <div className="mb-4 space-y-2">
        <ErrorNote error={save.error ?? remove.error} />
        {dirty && problem && <p className="text-sm text-spark">{problem}</p>}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="min-w-0 space-y-6">
          {stored && <AdaptationPanel profile={stored} onApplied={applySuggestion} />}
          <ProfileForm
            spec={draft}
            onChange={setDraft}
            look={stored ? <ProfileLookPicker profile={stored} /> : null}
          />
        </div>
        <div className="lg:sticky lg:top-9 lg:self-start">
          <PreviewPanel draft={draft} saved={saved} isDirty={dirty} />
        </div>
      </div>

      {/* The save button at the top is a screen away from a slider at the
          bottom: unsaved edits keep a bar of their own in view. */}
      {dirty && <div aria-hidden className="h-24" />}
      <AnimatePresence>
        {dirty && (
          <motion.div
            role="region"
            aria-label="Несохранённые правки"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: 0.2, ease: EASE }}
            className="fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20 mx-auto flex max-w-xl flex-wrap items-center gap-x-2 gap-y-1 rounded-2xl bg-inverse-surface py-2 pr-2 pl-4 text-sm text-inverse-on-surface shadow-elevation-3 md:bottom-6"
          >
            {/* On a phone the buttons go under the text rather than squeeze it into a column. */}
            <span className="min-w-44 flex-1 py-1">{problem ?? 'Правки не сохранены'}</span>
            <div className="ml-auto flex shrink-0 items-center gap-2">
              {saved && (
                <button
                  type="button"
                  onClick={() => setDraft(saved)}
                  className="shrink-0 rounded-full px-3 py-2 font-medium hover:bg-inverse-on-surface/10"
                >
                  Отменить
                </button>
              )}
              <Button
                variant="primary"
                size="sm"
                icon={<Save size={15} />}
                disabled={Boolean(problem)}
                isBusy={save.isPending}
                onClick={() => persist()}
              >
                Сохранить
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
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
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
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
