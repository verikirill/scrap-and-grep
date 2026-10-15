import { useLocation, useNavigate } from 'react-router'
import { ErrorIllustration } from '../components/ErrorIllustration'
import { ChevronLeft } from '../components/icons'
import { Button } from '../components/ui'

/** An address the app has no page for: the cat goes on looking, the reader goes home or back. */
export function NotFoundPage() {
  const navigate = useNavigate()
  const location = useLocation()
  // The first page of this tab has nowhere in the app to go back to: home instead.
  const goBack = () => (location.key === 'default' ? navigate('/') : navigate(-1))
  return (
    <section className="flex flex-col items-center px-4 py-8 text-center sm:py-12">
      <ErrorIllustration status={404} isEager />
      <p className="mt-6 text-6xl font-semibold tracking-tight tabular-nums text-muted">404</p>
      <h1 className="mt-3 text-xl font-semibold">Такой страницы нет</h1>
      <p className="mt-1.5 max-w-md text-sm text-muted">
        Возможно, в адресе опечатка или страницу перенесли.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button variant="cta" onClick={() => navigate('/')}>
          На главную
        </Button>
        <Button variant="secondary" icon={<ChevronLeft size={18} />} onClick={goBack}>
          Назад
        </Button>
      </div>
    </section>
  )
}
