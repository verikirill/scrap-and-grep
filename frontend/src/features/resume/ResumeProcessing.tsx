import { FileText } from '../../components/icons'
import { motion } from 'motion/react'
import { Card } from '../../components/ui'

type Props = {
  usesModel: boolean
  usesDocling: boolean
}

/** Shown while the worker reads the resume. No fake percentages: the wait is honest. */
export function ResumeProcessing({ usesModel, usesDocling }: Props) {
  return (
    <Card className="flex flex-col items-center px-6 py-12 text-center">
      <div
        role="status"
        aria-label="Читаем резюме"
        className="relative mb-5 grid size-16 place-items-center overflow-hidden rounded-2xl bg-surface-container text-on-primary-container"
      >
        <FileText size={28} />
        <motion.span
          className="absolute inset-x-0 top-0 h-0.5 bg-primary"
          animate={{ y: [0, 64, 0] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>
      <h2 className="text-base font-semibold">Читаем резюме</h2>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
        {usesDocling ? 'Разбираем вёрстку документа, ' : 'Достаём текст, '}
        убираем контакты и подбираем темы новостей.{' '}
        {usesModel
          ? 'С языковой моделью это занимает 10–30 секунд.'
          : 'Без модели это занимает пару секунд.'}
      </p>
    </Card>
  )
}
