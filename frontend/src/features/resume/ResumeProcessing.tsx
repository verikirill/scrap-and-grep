import { ScanText } from '../../components/icons'
import { Pulse } from '../../components/loading'
import { Card, IconTile } from '../../components/ui'

type Props = {
  usesModel: boolean
  usesDocling: boolean
}

/** Shown while the worker reads the resume. No fake percentages: the wait is honest. */
export function ResumeProcessing({ usesModel, usesDocling }: Props) {
  return (
    <Card className="flex flex-col items-center px-6 py-12 text-center">
      {/* The document in its tile, with a pulse in the corner while it is read. */}
      <div role="status" aria-busy="true" aria-label="Читаем резюме" className="relative mb-5">
        <IconTile icon={<ScanText />} />
        <Pulse className="absolute -top-1 -right-1" />
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
