import { FileText, RotateCcw } from '../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { EASE } from '../components/tokens'
import { Loading, Skeleton, SkeletonList, SkeletonText } from '../components/loading'
import { Button, Card, EmptyState, ErrorNote, ErrorState, PageHeader } from '../components/ui'
import { BuildPanel } from '../features/digest/BuildPanel'
import { DigestView } from '../features/digest/DigestView'
import { History } from '../features/digest/History'
import { DigestHeading } from '../features/digest/DigestHeading'
import { twinOf } from '../lib/digestPairs'
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
import { sameKind } from '../lib/digestPairs'
import { useMediaQuery } from '../lib/useMediaQuery'

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
  const summary = digests.data?.find((item) => item.id === activeId)
  const isBuilding = current?.status === 'queued' || current?.status === 'running'

  // On a phone the form is a screen tall: with an issue open it folds into
  // one button, unless a profile was sent here to be built.
  const isPhone = useMediaQuery('(max-width: 767px)')
  const [isBuilderOpen, setIsBuilderOpen] = useState(false)
  const showBuilder = !isPhone || !activeId || isBuilderOpen || Boolean(search.get('profile'))
  // An issue just asked for is brought into view once, when its progress card
  // mounts (after the previous issue has left): on a phone it would otherwise
  // be below the fold, and nothing would seem to happen.
  const [createdId, setCreatedId] = useState<string | null>(null)
  const showProgress = (node: HTMLDivElement | null) => {
    if (!node || createdId === null || createdId !== current?.id) return
    setCreatedId(null)
    if (isPhone) node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  // The issue built before this one for the same profile, for the compare link.
  // A management issue is compared with management ones, not with the
  // specialist's issue built together with it.
  const previous = digests.data?.find(
    (other) =>
      current &&
      other.status === 'done' &&
      sameKind(other, current) &&
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
      { profileId: current.profile_id, period: { days: periodDays(current) } },
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
          {profiles.data && showBuilder && (
            <BuildPanel
              profiles={profiles.data}
              initialProfileId={search.get('profile')}
              isBuilding={isBuilding}
              onCreated={(id) => {
                setCreatedId(id)
                setIsBuilderOpen(false)
                navigate(`/digests/${id}`)
              }}
            />
          )}
          {profiles.data && !showBuilder && (
            <Button
              variant="cta"
              isBusy={isBuilding}
              onClick={() => setIsBuilderOpen(true)}
              className="w-full"
            >
              {isBuilding ? 'Собираем выпуск' : 'Новый выпуск'}
            </Button>
          )}
          <ErrorNote error={profiles.error ?? digests.error ?? remove.error ?? retry.error} />

          {digest.isError && (
            <Card>
              <ErrorState
                title="Не удалось открыть выпуск"
                error={digest.error}
                action={<Button onClick={() => navigate('/')}>К последнему выпуску</Button>}
              />
            </Card>
          )}

          {/* Outside the presence below and keyed by the digest: the old
              header leaves and the new one comes in the same render, which is
              what lets their titles morph into the history rows and back. */}
          {summary && (
            <DigestHeading
              key={summary.id}
              summary={summary}
              twin={twinOf(summary, digests.data ?? [])}
              onOpen={(id) => navigate(`/digests/${id}`)}
            />
          )}

          <AnimatePresence mode="wait">
            {digest.isLoading && activeId && (
              <motion.div key="loading" exit={{ opacity: 0 }}>
                <Loading label="Открываем выпуск" className="space-y-3">
                  <div aria-hidden className="rounded-3xl bg-surface p-6 shadow-surface">
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="mt-3 h-6 w-2/3" />
                    <SkeletonText lines={3} className="mt-4" />
                  </div>
                  <SkeletonList count={3} hasMark={false} />
                </Loading>
              </motion.div>
            )}

            {current && isBuilding && (
              <motion.div
                key={`progress-${current.id}`}
                ref={showProgress}
                className="scroll-mt-20"
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
                <Card>
                  <ErrorState
                    title="Не удалось собрать выпуск"
                    action={
                      current.profile_id && (
                        <Button
                          variant="primary"
                          icon={<RotateCcw size={15} />}
                          isBusy={retry.isPending}
                          onClick={handleRetry}
                        >
                          Собрать заново
                        </Button>
                      )
                    }
                  >
                    {current.error ?? 'Причина неизвестна.'}
                  </ErrorState>
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
                    Выберите профиль и нажмите «Собрать выпуск»: за неделю новостей это несколько
                    секунд в автономном режиме и пара минут с языковой моделью.
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
          <h2 className="mb-2.5 px-1 text-xs font-semibold tracking-wide text-muted uppercase">
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
            <Loading label="Загружаем историю" className="space-y-2">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </Loading>
          )}
        </motion.aside>
      </div>
    </>
  )
}
