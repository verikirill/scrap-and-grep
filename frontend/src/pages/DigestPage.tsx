import { FileText, RotateCcw } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { EASE } from '../components/tokens'
import { Button, Card, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { BuildPanel } from '../features/digest/BuildPanel'
import { DigestView } from '../features/digest/DigestView'
import { History } from '../features/digest/History'
import { ProgressCard } from '../features/digest/ProgressCard'
import type { DigestSummary } from '../lib/api'
import {
  useCreateDigest,
  useDeleteDigest,
  useDigest,
  useDigestProgress,
  useDigests,
  useProfiles,
} from '../lib/queries'

const DAY_MS = 86_400_000

/** The period a digest was built for, in whole days, to rebuild it as it was. */
function periodDays(digest: DigestSummary): number {
  const span = new Date(digest.period_end).getTime() - new Date(digest.period_start).getTime()
  return Math.min(90, Math.max(1, Math.round(span / DAY_MS)))
}

export function DigestPage() {
  const { digestId } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const profiles = useProfiles()
  const digests = useDigests()
  const remove = useDeleteDigest()
  const retry = useCreateDigest()

  const activeId = digestId ?? digests.data?.[0]?.id
  const digest = useDigest(activeId)
  const progress = useDigestProgress(digest.data)

  const current = digest.data
  const isBuilding = current?.status === 'queued' || current?.status === 'running'
  // The issue built before this one for the same profile, for the compare link.
  const previous = digests.data?.find(
    (other) =>
      current &&
      other.id !== current.id &&
      other.status === 'done' &&
      other.profile_id === current.profile_id &&
      other.created_at < current.created_at,
  )

  const handleDelete = (id: string) => {
    remove.mutate(id, {
      onSuccess: () => {
        if (id === activeId) navigate('/')
      },
    })
  }

  const handleRetry = () => {
    if (!current?.profile_id) return
    retry.mutate(
      { profileId: current.profile_id, days: periodDays(current) },
      { onSuccess: (created) => navigate(`/digests/${created.id}`) },
    )
  }

  return (
    <>
      <PageHeader
        title="Дайджест"
        subtitle="Выберите профиль и период. Ассистент найдёт публикации по интересам, уберёт повторы, сгруппирует по темам и напишет выжимки со ссылками на источники."
      />
      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0 space-y-6">
          {profiles.data && (
            <BuildPanel
              profiles={profiles.data}
              initialProfileId={search.get('profile')}
              onCreated={(id) => navigate(`/digests/${id}`)}
            />
          )}
          <ErrorNote error={profiles.error ?? digests.error ?? remove.error ?? retry.error} />

          {digest.isError && (
            <Card className="p-6">
              <h2 className="text-base font-semibold">Выпуск не открылся</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {digest.error instanceof Error ? digest.error.message : 'Неизвестная ошибка.'}
              </p>
              <Button className="mt-4" onClick={() => navigate('/')}>
                К последнему выпуску
              </Button>
            </Card>
          )}

          <AnimatePresence mode="wait">
            {digest.isLoading && activeId && (
              <motion.div key="loading" exit={{ opacity: 0 }} className="space-y-3">
                <div className="skeleton h-40" />
                <div className="skeleton h-24" />
              </motion.div>
            )}

            {current && isBuilding && (
              <motion.div
                key={`progress-${current.id}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, ease: EASE }}
              >
                <ProgressCard digest={current} event={progress} />
              </motion.div>
            )}

            {current?.status === 'failed' && (
              <motion.div
                key={`failed-${current.id}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Card className="p-6">
                  <h2 className="text-base font-semibold">Выпуск собрать не удалось</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {current.error ?? 'Причина неизвестна.'}
                  </p>
                  {current.profile_id && (
                    <Button
                      className="mt-4"
                      icon={<RotateCcw size={15} />}
                      isBusy={retry.isPending}
                      onClick={handleRetry}
                    >
                      Собрать заново
                    </Button>
                  )}
                </Card>
              </motion.div>
            )}

            {current?.status === 'done' && (
              <motion.div
                key={`done-${current.id}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EASE }}
              >
                <DigestView digest={current} previousId={previous?.id} />
              </motion.div>
            )}

            {!activeId && digests.isSuccess && (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Card>
                  <EmptyState icon={<FileText size={22} />} title="Выпусков пока нет">
                    Соберите первый: на неделю публикаций уходит от нескольких секунд в автономном
                    режиме до пары минут с языковой моделью.
                  </EmptyState>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* layoutScroll: rows animate inside a scrolling box, so their
            positions must be measured relative to its scroll offset. */}
        <motion.aside
          layoutScroll
          className="xl:sticky xl:top-9 xl:max-h-[calc(100dvh-4.5rem)] xl:self-start xl:overflow-y-auto"
        >
          <h2 className="mb-2.5 px-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            История
          </h2>
          {digests.data ? (
            <History
              digests={digests.data}
              activeId={activeId}
              onSelect={(id) => navigate(`/digests/${id}`)}
              onDelete={handleDelete}
            />
          ) : (
            <div className="space-y-2">
              <div className="skeleton h-16" />
              <div className="skeleton h-16" />
            </div>
          )}
        </motion.aside>
      </div>
    </>
  )
}
