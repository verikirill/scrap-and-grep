import { Link, useNavigate } from 'react-router'
import { DottedPage } from '../components/DottedPage'
import { LogoMark, Wordmark } from '../components/Logo'
import { buttonClass } from '../components/tokens'
import { ResumeFlow } from '../features/resume/ResumeFlow'
import { useMe } from '../lib/queries'

/** A profile from the resume: upload it, review the suggested topics, open the feed. */
export function WelcomePage() {
  const me = useMe()
  const navigate = useNavigate()

  return (
    <DottedPage>
      <div className="mx-auto max-w-2xl px-5 py-8 sm:py-12">
        <header className="mb-10 flex items-center justify-between">
          <span className="flex items-center gap-2.5">
            <LogoMark size={36} />
            <Wordmark className="text-[17px]" />
          </span>
          <Link to="/profiles" className={buttonClass('secondary', 'sm')}>
            Настроить интересы вручную
          </Link>
        </header>

        <h1 className="font-serif text-[30px] leading-tight font-semibold tracking-tight text-balance">
          {me.data
            ? `${me.data.display_name}, расскажите о своей работе`
            : 'Расскажите о своей работе'}
        </h1>
        <p className="mt-2 mb-7 text-sm text-muted">
          Загрузите резюме, и сервис определит специализацию и предложит темы публикаций. Лента и
          выпуски сразу подстроятся под ваши задачи.
        </p>

        <ResumeFlow saveLabel="Создать профиль и открыть ленту" onSaved={() => navigate('/feed')} />
      </div>
    </DottedPage>
  )
}
