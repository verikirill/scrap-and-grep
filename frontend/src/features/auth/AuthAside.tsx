import { LogoMark, Wordmark } from '../../components/Logo'
import { AuthRadar } from './AuthRadar'
import { ScrambleText } from './ScrambleText'
import { TailVisual } from './TailVisual'

// The readers the brand side names in turn: the profiles the service ships with.
const ROLES = [
  'инженера АСУ ТП',
  'руководителя ИТ',
  'дежурного SOC',
  'директора по цифре',
  'аналитика ИБ',
]

/**
 * The dark brand side of the sign-in pages: the radar, the cat and the reader
 * the digest is for. Shown from laptop width up; the moving parts mount only there.
 * One window tall and no taller: it never stretches the page into a scroll.
 */
export function AuthAside({ isWide }: { isWide: boolean }) {
  // The brand side keeps its dark look in both themes: it is a picture, not a surface.
  return (
    <aside className="relative isolate hidden overflow-hidden bg-[#0b0f17] px-12 py-10 text-white short:py-7 lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col">
      {/* The radar sweeps the whole dark side from its middle; mounted only
          where the side is visible. */}
      {isWide && <AuthRadar />}
      <div className="flex items-center gap-2.5">
        <LogoMark size={32} />
        <Wordmark className="text-[15px]" />
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center py-10 short:py-5">
        {/* Mounted only where it is visible: animations hidden by CSS still run. */}
        {isWide && <TailVisual />}
      </div>
      <div className="max-w-md">
        {/* The reader the digest is for changes, decoded like a match in
            the terminal above; a screen reader hears the sentence once. */}
        <p
          aria-label="Новости ИТ и ИБ под вашу работу"
          className="font-serif text-[28px] leading-tight font-semibold"
        >
          <span aria-hidden>Новости ИТ и ИБ</span>
          <span aria-hidden className="mt-1 flex items-baseline gap-2.5">
            <span>для</span>
            <ScrambleText words={ROLES} className="auth-role" />
          </span>
        </p>
        <p className="mt-3 text-sm leading-relaxed text-white/60">
          Сервис читает больше 100 источников по ИТ, информационной безопасности и энергетике,
          фильтрует публикации по вашим интересам и собирает из них выпуски со ссылками. Резюме
          помогает настроить отбор с первой минуты.
        </p>
      </div>
    </aside>
  )
}
