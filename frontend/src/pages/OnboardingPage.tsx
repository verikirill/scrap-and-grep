import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { FileText, Layers, PenLine } from '../components/icons'
import { LogoMark, Wordmark } from '../components/Logo'
import { EASE } from '../components/tokens'
import { Button, Card, ErrorNote } from '../components/ui'
import { useRadioKeys } from '../components/useRadioKeys'
import { ChoiceCard } from '../features/onboarding/ChoiceCard'
import { TemplatePicker } from '../features/onboarding/TemplatePicker'
import { ProfileAvatar } from '../features/profiles/ProfileLook'
import { ResumeFlow } from '../features/resume/ResumeFlow'
import type { Profile } from '../lib/api'
import { plural } from '../lib/format'
import { needsOnboarding } from '../lib/onboarding'
import { useCreateDigest, useFinishOnboarding, useMe, useProfiles } from '../lib/queries'

const STEPS = [
  { key: 'intro', label: 'Знакомство' },
  { key: 'profile', label: 'Профиль интересов' },
  { key: 'digest', label: 'Первый выпуск' },
] as const
type Step = (typeof STEPS)[number]['key']

const METHODS = [
  {
    key: 'resume',
    icon: FileText,
    title: 'По резюме',
    text: 'Загрузите файл, и сервис сам предложит темы под вашу работу.',
  },
  {
    key: 'template',
    icon: Layers,
    title: 'Готовый шаблон',
    text: 'Профиль для типичной роли в энергетике, ИТ или ИБ.',
  },
  {
    key: 'manual',
    icon: PenLine,
    title: 'Вручную',
    text: 'Темы, ключевые слова и исключения задаёте сами.',
  },
] as const
type Method = (typeof METHODS)[number]['key']

const STEP_MOTION = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.3, ease: EASE },
}

function StepBar({ step }: { step: Step }) {
  const current = STEPS.findIndex((item) => item.key === step)
  return (
    <div className="mb-8">
      <ol aria-label="Шаги знакомства" className="flex gap-1.5">
        {STEPS.map((item, index) => (
          <li
            key={item.key}
            aria-current={index === current ? 'step' : undefined}
            className={clsx(
              'h-1 flex-1 rounded-full transition-colors duration-300',
              index <= current ? 'bg-accent' : 'bg-surface-secondary',
            )}
          >
            <span className="sr-only">{item.label}</span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-muted">
        Шаг {current + 1} из {STEPS.length}: {STEPS[current].label.toLowerCase()}
      </p>
    </div>
  )
}

const DEFAULT_DAYS = 7

/** "за последние сутки", "за последние 3 дня", "за последние 7 дней". */
const periodText = (days: number) =>
  days === 1
    ? 'за последние сутки'
    : `за последние ${days} ${plural(days, ['день', 'дня', 'дней'])}`

type MethodProps = {
  profiles: Profile[]
  onProfile: (profile: Profile) => void
  onManual: () => void
  isLeaving: boolean
}

/** The second step: a profile from the resume, from a template, or by hand. */
function ProfileStep({ profiles, onProfile, onManual, isLeaving }: MethodProps) {
  const [method, setMethod] = useState<Method | null>(null)
  const chosen = METHODS.findIndex((item) => item.key === method)
  const keys = useRadioKeys(METHODS.length, chosen, (index) => setMethod(METHODS[index].key))
  const existing = profiles[0]

  return (
    <>
      <h1 className="font-serif text-[30px] leading-tight font-semibold tracking-tight text-balance">
        Первый профиль интересов
      </h1>
      <p className="mt-2 mb-6 text-sm text-muted">
        Профиль подсказывает сервису, какие темы важны в вашей работе. Потом его можно поправить в
        разделе «Интересы».
      </p>

      {existing && (
        <Card variant="filled" className="mb-5 flex flex-wrap items-center gap-3 p-4">
          <ProfileAvatar profile={existing} size={36} />
          <p className="min-w-0 flex-1 text-sm">У вас уже есть профиль «{existing.spec.name}».</p>
          <Button size="sm" variant="tonal" onClick={() => onProfile(existing)}>
            Продолжить с ним
          </Button>
        </Card>
      )}

      <div
        role="radiogroup"
        aria-label="Как создать профиль"
        onKeyDown={keys.onKeyDown}
        className="grid gap-2 sm:grid-cols-3"
      >
        {METHODS.map((item, index) => (
          <ChoiceCard
            key={item.key}
            {...keys.itemProps(index)}
            isChosen={item.key === method}
            onChoose={() => setMethod(item.key)}
            leading={
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-soft-foreground">
                <item.icon size={18} />
              </span>
            }
            title={item.title}
          >
            {item.text}
          </ChoiceCard>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {method && (
          <motion.div key={method} {...STEP_MOTION} className="mt-6">
            {method === 'resume' && <ResumeFlow saveLabel="Создать профиль" onSaved={onProfile} />}
            {method === 'template' && <TemplatePicker onCreated={onProfile} />}
            {method === 'manual' && (
              <Card className="p-5 sm:p-6">
                <p className="text-sm text-muted">
                  В редакторе сразу видно, какие публикации попадут в выпуск. Когда профиль будет
                  готов, нажмите там «Собрать выпуск».
                </p>
                <Button variant="primary" className="mt-4" isBusy={isLeaving} onClick={onManual}>
                  Открыть редактор
                </Button>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

/**
 * The first-run introduction: what the service does, the first profile of
 * interests, the first digest. Shown once to a newly registered reader; once
 * finished or skipped it is marked on the server and does not come back by
 * itself. The account page opens it again on demand.
 */
export function OnboardingPage() {
  const navigate = useNavigate()
  const me = useMe()
  const profiles = useProfiles()
  const finish = useFinishOnboarding()
  const build = useCreateDigest()
  const [step, setStep] = useState<Step>('intro')
  const [profile, setProfile] = useState<Profile | null>(null)

  /** Leave for a page of the app; the first time, the introduction is marked as done. */
  const leave = (to: string) => {
    if (needsOnboarding(me.data)) finish.mutate(undefined, { onSuccess: () => navigate(to) })
    else navigate(to)
  }

  const toDigest = (made: Profile) => {
    setProfile(made)
    setStep('digest')
  }

  // Marked first: a retry after a failed build must not start a second issue.
  const startDigest = async (made: Profile) => {
    try {
      if (needsOnboarding(me.data)) await finish.mutateAsync()
      const created = await build.mutateAsync({
        profileId: made.id,
        period: { days: made.defaults.period_days },
      })
      navigate(`/digests/${created.id}`)
    } catch {
      // Either failure is on screen: the mutations keep their errors for ErrorNote.
    }
  }

  const days = profile?.defaults.period_days ?? DEFAULT_DAYS
  return (
    <div className="mx-auto min-h-dvh max-w-2xl px-4 py-8 sm:px-5 sm:py-12">
      <header className="mb-8 flex items-center justify-between gap-3">
        <span className="flex items-center gap-2.5">
          <LogoMark size={36} />
          <Wordmark className="text-[17px]" />
        </span>
        <Button size="sm" variant="ghost" disabled={finish.isPending} onClick={() => leave('/')}>
          Пропустить
        </Button>
      </header>

      <StepBar step={step} />
      <div className="mb-4">
        <ErrorNote error={finish.error} />
      </div>

      <AnimatePresence mode="wait">
        {step === 'intro' && (
          <motion.section key="intro" {...STEP_MOTION} aria-labelledby="onboarding-title">
            <h1
              id="onboarding-title"
              className="font-serif text-[30px] leading-tight font-semibold tracking-tight text-balance"
            >
              {me.data ? `Здравствуйте, ${me.data.display_name}` : 'Здравствуйте'}
            </h1>
            <p className="mt-3 text-base text-pretty">
              Scrap&Grep читает больше 100 источников по ИТ, информационной безопасности и
              энергетике и собирает из них короткие выпуски под ваши задачи.
            </p>
            <Card variant="filled" className="mt-6 p-5">
              <p className="text-sm font-semibold">За пару минут настроим главное</p>
              <ol className="mt-3 space-y-2 text-sm text-muted">
                <li>1. Профиль интересов: какие темы важны в работе.</li>
                <li>2. Первый выпуск: главное по вашим темам со ссылками на источники.</li>
              </ol>
              <p className="mt-3 text-xs text-muted">Всё это можно поменять позже.</p>
            </Card>
            <Button
              variant="cta"
              className="mt-7 w-full sm:w-auto"
              onClick={() => setStep('profile')}
            >
              Начать
            </Button>
          </motion.section>
        )}

        {step === 'profile' && (
          <motion.section key="profile" {...STEP_MOTION}>
            <ProfileStep
              profiles={profiles.data ?? []}
              onProfile={toDigest}
              onManual={() => leave('/profiles')}
              isLeaving={finish.isPending}
            />
            <Button variant="ghost" className="mt-6" onClick={() => setStep('intro')}>
              Назад
            </Button>
          </motion.section>
        )}

        {step === 'digest' && profile && (
          <motion.section key="digest" {...STEP_MOTION}>
            <h1 className="font-serif text-[30px] leading-tight font-semibold tracking-tight text-balance">
              Первый выпуск
            </h1>
            <p className="mt-2 mb-6 text-sm text-muted">
              Ассистент найдёт публикации по вашим темам {periodText(days)}, уберёт повторы и
              напишет короткие выжимки со ссылками на источники. Это занимает от нескольких секунд
              до пары минут.
            </p>
            <Card className="flex items-center gap-3 p-5">
              <ProfileAvatar profile={profile} size={44} />
              <div className="min-w-0">
                <p className="text-sm font-semibold break-words">{profile.spec.name}</p>
                <p className="text-sm text-muted">
                  {profile.spec.interests.length}{' '}
                  {plural(profile.spec.interests.length, ['тема', 'темы', 'тем'])}
                </p>
              </div>
            </Card>
            <div className="mt-4">
              <ErrorNote error={build.error} />
            </div>
            <div className="mt-6 flex flex-wrap gap-2">
              <Button
                variant="cta"
                className="w-full sm:w-auto"
                isBusy={build.isPending || finish.isPending}
                onClick={() => void startDigest(profile)}
              >
                Собрать выпуск
              </Button>
              <Button
                variant="ghost"
                className="w-full sm:w-auto"
                disabled={build.isPending || finish.isPending}
                onClick={() => leave('/feed')}
              >
                Позже, открыть ленту
              </Button>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  )
}
