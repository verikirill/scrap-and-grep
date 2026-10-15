import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { ShieldCheck } from '../../components/icons'
import { Loading, Skeleton } from '../../components/loading'
import { EASE } from '../../components/tokens'
import { Button, Card, ErrorNote } from '../../components/ui'
import type { Profile, ProfileSpec, Resume } from '../../lib/api'
import {
  isResumeStuck,
  useMeta,
  useResume,
  useResumeMutations,
  useSaveProfile,
} from '../../lib/queries'
import { ResumeDrop } from './ResumeDrop'
import { ResumeFactsView } from './ResumeFactsView'
import { ResumeProcessing } from './ResumeProcessing'
import { SuggestionEditor } from './SuggestionEditor'

const STEP_MOTION = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.3, ease: EASE },
}

type Props = {
  /** The label of the button that saves the profile. */
  saveLabel: string
  /** The profile built from the resume is saved. */
  onSaved: (profile: Profile) => void
}

type ReviewProps = Props & {
  resume: Resume
  suggestion: ProfileSpec
  onReplace: () => void
}

/**
 * Review of the suggested profile. Mounted per upload (keyed by its time), so
 * the draft starts from the suggestion and edits are not lost on a refetch.
 */
function Review({ resume, suggestion, onReplace, saveLabel, onSaved }: ReviewProps) {
  const save = useSaveProfile()
  const [spec, setSpec] = useState(suggestion)
  const [kept, setKept] = useState(() => suggestion.interests.map((interest) => interest.id))

  const create = () => {
    const interests = spec.interests.filter((interest) => kept.includes(interest.id))
    save.mutate({ id: null, spec: { ...spec, interests } }, { onSuccess: onSaved })
  }

  return (
    <div className="space-y-5">
      <Card className="p-6">
        {resume.facts && <ResumeFactsView resume={resume} facts={resume.facts} />}
        <button
          type="button"
          onClick={onReplace}
          className="mt-4 text-sm text-muted underline decoration-outline-variant underline-offset-4 hover:text-foreground"
        >
          Загрузить другой файл
        </button>
      </Card>
      <Card className="p-6">
        <h2 className="text-base font-semibold">Профиль интересов</h2>
        <p className="mt-1 mb-5 text-sm text-muted">
          Выберите темы, нужные для работы. Ключевые слова, важность и исключения можно настроить
          позже в разделе «Интересы».
        </p>
        <SuggestionEditor spec={spec} kept={kept} onSpecChange={setSpec} onKeptChange={setKept} />
        <div className="mt-6 space-y-3">
          <ErrorNote error={save.error} />
          <Button
            variant="cta"
            className="w-full sm:w-auto"
            isBusy={save.isPending}
            disabled={kept.length === 0 || spec.name.trim().length < 2}
            onClick={create}
          >
            {saveLabel}
          </Button>
        </div>
      </Card>
    </div>
  )
}

/**
 * From a resume to a profile: upload, the wait while it is read, then the
 * review of the suggested topics. Shared by the resume page and the
 * first-run introduction.
 */
export function ResumeFlow({ saveLabel, onSaved }: Props) {
  const meta = useMeta()
  const resume = useResume()
  const { upload } = useResumeMutations()
  // Set when the reader asks to replace a resume that is already analysed.
  const [isReplacing, setIsReplacing] = useState(false)

  const current = resume.data
  const isStuck = isResumeStuck(current)
  const isProcessing = upload.isPending || (current?.status === 'processing' && !isStuck)
  const isReady = current?.status === 'ready' && current.suggestion && !isReplacing && !isProcessing
  const failure = current?.status === 'failed' && !upload.isPending ? current.error : null

  return (
    <AnimatePresence mode="wait">
      {resume.isPending ? (
        <motion.div key="loading" {...STEP_MOTION}>
          <Loading label="Проверяем, есть ли резюме" className="space-y-4">
            <Skeleton className="h-44 rounded-3xl" />
            <Skeleton className="h-4 w-3/4" />
          </Loading>
        </motion.div>
      ) : isProcessing ? (
        <motion.div key="processing" {...STEP_MOTION}>
          <ResumeProcessing
            usesModel={meta.data?.llm_provider === 'ollama'}
            usesDocling={meta.data?.resume_parser === 'docling'}
          />
        </motion.div>
      ) : isReady && current?.suggestion ? (
        <motion.div key={`review-${current.created_at}`} {...STEP_MOTION}>
          <Review
            resume={current}
            suggestion={current.suggestion}
            onReplace={() => setIsReplacing(true)}
            saveLabel={saveLabel}
            onSaved={onSaved}
          />
        </motion.div>
      ) : (
        <motion.div key="upload" {...STEP_MOTION} className="space-y-4">
          <ResumeDrop
            meta={meta.data}
            isBusy={upload.isPending}
            onFile={(file) => upload.mutate(file, { onSuccess: () => setIsReplacing(false) })}
          />
          <ErrorNote error={upload.error ?? resume.error} />
          {isStuck && (
            <p role="alert" className="rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
              Резюме разбирается дольше обычного. Попробуйте загрузить файл ещё раз.
            </p>
          )}
          {failure && (
            <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {failure}
            </p>
          )}
          <p className="flex items-start gap-2 text-xs text-muted">
            <ShieldCheck size={15} className="mt-px shrink-0 text-success" />
            Файл удаляется сразу после обработки. Личные данные (имя, контакты, адрес) вырезаются до
            анализа. В системе остаются только должность, навыки и темы - их можно удалить в разделе
            «Аккаунт».
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
