import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { ArtTile } from '../components/ArtTile'
import { BrandCat } from '../components/BrandCat'
import { DottedPage } from '../components/DottedPage'
import { AutoAwesome, ChevronLeft, ChevronRight, Compass, Target } from '../components/icons'
import { LogoMark, Wordmark } from '../components/Logo'
import { Button, Card, ErrorNote } from '../components/ui'
import { IntroStep } from '../features/onboarding/IntroStep'
import { ProfileStep } from '../features/onboarding/ProfileStep'
import { SectionStep } from '../features/onboarding/SectionStep'
import { SECTIONS } from '../features/onboarding/sections'
import { FocusStepContext } from '../features/onboarding/focus'
import { StepHeading } from '../features/onboarding/StepHeading'
import { TourStepper } from '../features/onboarding/TourStepper'
import type { StepMark } from '../features/onboarding/TourStepper'
import { SLIDE } from '../features/onboarding/motion'
import { useTourKeys } from '../features/onboarding/useTourKeys'
import { ProfileAvatar } from '../features/profiles/ProfileLook'
import type { Profile } from '../lib/api'
import { plural } from '../lib/format'
import { needsOnboarding } from '../lib/onboarding'
import { useCreateDigest, useFinishOnboarding, useMe, useProfiles } from '../lib/queries'

/** The greeting, every section in the order of the sidebar, then the two working steps. */
const STEPS: readonly StepMark[] = [
  { key: 'intro', label: 'Знакомство', icon: Compass },
  ...SECTIONS.map(({ key, label, icon }) => ({ key, label, icon })),
  { key: 'profile', label: 'Профиль', icon: Target },
  { key: 'first-digest', label: 'Первый выпуск', icon: AutoAwesome },
]
const PROFILE_STEP = STEPS.length - 2
const DIGEST_STEP = STEPS.length - 1

const DEFAULT_DAYS = 7

/** "за последние сутки", "за последние 3 дня", "за последние 7 дней". */
const periodText = (days: number) =>
  days === 1
    ? 'за последние сутки'
    : `за последние ${days} ${plural(days, ['день', 'дня', 'дней'])}`

function KeyHint() {
  const key = 'rounded-md bg-default px-1.5 py-0.5 font-sans text-[11px] text-foreground'
  return (
    <p className="mx-auto hidden items-center gap-1.5 text-xs text-muted lg:flex">
      <kbd className={key}>←</kbd>
      <kbd className={key}>→</kbd>
      листают шаги, <kbd className={key}>Esc</kbd> пропускает
    </p>
  )
}

/**
 * The first-run introduction: a greeting, a short tour of every section of the
 * app, the first profile of interests and the first digest. Shown once to a
 * newly registered reader; once finished or skipped it is marked on the server
 * and does not come back by itself. The account page opens it again on demand.
 */
export function OnboardingPage() {
  const navigate = useNavigate()
  const me = useMe()
  const profiles = useProfiles()
  const finish = useFinishOnboarding()
  const build = useCreateDigest()
  const [[index, direction], setPlace] = useState<[number, number]>([0, 1])
  const [hasMoved, setHasMoved] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const isBusy = finish.isPending || build.isPending

  /** Leave for a page of the app; the first time, the introduction is marked as done. */
  const leave = (to: string) => {
    if (needsOnboarding(me.data)) finish.mutate(undefined, { onSuccess: () => navigate(to) })
    else navigate(to)
  }
  const skip = () => {
    if (!isBusy) leave('/')
  }

  // The first digest needs a profile: until one is chosen its step stays closed.
  const canOpen = (target: number) =>
    target <= PROFILE_STEP || (target === DIGEST_STEP && profile !== null)

  const goTo = (target: number) => {
    if (target === index || !canOpen(target)) return
    setPlace([target, Math.sign(target - index)])
    setHasMoved(true)
    // On a phone the reader pressed «Далее» at the bottom: the new step starts at its top.
    if (window.scrollY > 0) {
      const isCalm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      window.scrollTo({ top: 0, behavior: isCalm ? 'auto' : 'smooth' })
    }
  }

  const next = index < DIGEST_STEP && canOpen(index + 1) ? () => goTo(index + 1) : undefined
  const back = index > 0 ? () => goTo(index - 1) : undefined
  useTourKeys({ onNext: next, onBack: back, onSkip: skip })

  const toDigest = (made: Profile) => {
    setProfile(made)
    setPlace([DIGEST_STEP, 1])
    setHasMoved(true)
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

  const step = STEPS[index]
  const section = SECTIONS.find((item) => item.key === step.key)
  const days = profile?.defaults.period_days ?? DEFAULT_DAYS

  return (
    <DottedPage>
      <div className="mx-auto max-w-5xl px-4 py-4 sm:px-6 sm:py-10">
        <div className="rounded-[2rem] bg-surface shadow-surface">
          <div className="px-5 pt-5 sm:px-8 sm:pt-7">
            <header className="mb-5 flex items-center justify-between gap-3">
              <span className="flex items-center gap-2.5">
                <LogoMark size={36} />
                <Wordmark className="text-[17px]" />
              </span>
              <Button size="sm" variant="secondary" disabled={isBusy} onClick={skip}>
                Пропустить
              </Button>
            </header>
            <TourStepper steps={STEPS} current={index} canOpen={canOpen} onOpen={goTo} />
            <div className="mt-3">
              <ErrorNote error={finish.error} />
            </div>
          </div>

          <div className="overflow-x-clip px-5 pt-4 pb-6 sm:px-8 sm:pb-8 md:min-h-[27rem]">
            <FocusStepContext value={hasMoved}>
              <AnimatePresence mode="wait" custom={direction} initial={false}>
                <motion.section key={step.key} custom={direction} {...SLIDE}>
                  {step.key === 'intro' && (
                    <IntroStep
                      name={me.data?.display_name}
                      onStart={() => goTo(1)}
                      onSetup={() => goTo(PROFILE_STEP)}
                    />
                  )}

                  {section && <SectionStep section={section} me={me.data} />}

                  {step.key === 'profile' && (
                    <ProfileStep
                      profiles={profiles.data ?? []}
                      onProfile={toDigest}
                      onManual={() => leave('/profiles')}
                      isLeaving={finish.isPending}
                    />
                  )}

                  {step.key === 'first-digest' && profile && (
                    <div className="grid grid-cols-[minmax(0,1fr)] items-center gap-8 md:grid-cols-[minmax(0,1fr)_auto]">
                      <div>
                        <StepHeading kicker="Настройка">Первый выпуск</StepHeading>
                        <p className="mt-2 mb-6 max-w-xl text-sm text-muted">
                          Ассистент найдёт публикации по вашим темам {periodText(days)}, уберёт
                          повторы и напишет короткие выжимки со ссылками на источники. Это занимает
                          от нескольких секунд до пары минут.
                        </p>
                        <Card variant="filled" className="flex items-center gap-3 p-4">
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
                        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
                          <Button
                            variant="cta"
                            className="w-full sm:w-auto"
                            isBusy={isBusy}
                            onClick={() => void startDigest(profile)}
                          >
                            Собрать выпуск
                          </Button>
                          <Button
                            variant="ghost"
                            className="w-full sm:w-auto"
                            disabled={isBusy}
                            onClick={() => leave('/feed')}
                          >
                            Позже, открыть ленту
                          </Button>
                        </div>
                      </div>
                      <ArtTile className="hidden w-52 grid-cols-[minmax(0,1fr)] p-4 md:grid">
                        <BrandCat size={176} />
                      </ArtTile>
                    </div>
                  )}
                </motion.section>
              </AnimatePresence>
            </FocusStepContext>
          </div>

          {index > 0 && (
            <footer className="sticky bottom-0 z-10 flex items-center gap-3 rounded-b-[2rem] border-t border-separator bg-surface px-5 py-3.5 sm:px-8">
              <Button
                variant="secondary"
                icon={<ChevronLeft size={16} />}
                disabled={isBusy}
                onClick={back}
              >
                Назад
              </Button>
              <KeyHint />
              {next && (
                <Button variant="primary" className="ml-auto" onClick={next}>
                  Далее
                  <ChevronRight size={16} aria-hidden />
                </Button>
              )}
            </footer>
          )}
        </div>
      </div>
    </DottedPage>
  )
}
