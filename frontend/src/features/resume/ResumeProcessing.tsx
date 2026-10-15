import { Mascot } from '../../components/Mascot'
import { Card } from '../../components/ui'

type Props = {
  usesModel: boolean
  usesDocling: boolean
}

/** Shown while the worker reads the resume. No fake percentages: the wait is honest. */
export function ResumeProcessing({ usesModel, usesDocling }: Props) {
  return (
    <Card className="flex flex-col items-center px-6 py-12 text-center">
      {/* The cat reads the resume through its magnifier: no fake percentages. */}
      <div
        role="status"
        aria-busy="true"
        aria-label="Читаем резюме"
        className="mascot-tile mb-5 grid size-28 place-items-center"
      >
        <Mascot pose="searching" size={104} />
      </div>
      <h2 className="text-base font-semibold">Читаем резюме</h2>
      <p className="mt-1.5 max-w-sm text-sm text-muted">
        {usesDocling ? 'Разбираем структуру документа,' : 'Извлекаем текст,'}
        убираем контакты и подбираем темы новостей.{' '}
        {usesModel
          ? 'С языковой моделью это занимает 10–30 секунд.'
          : 'Без модели обработка занимает несколько секунд.'}
      </p>
    </Card>
  )
}
