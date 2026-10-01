import { Chip } from '../../components/ui'
import type { Resume, ResumeFacts } from '../../lib/api'

const SENIORITY_LABELS: Record<ResumeFacts['seniority'], string | null> = {
  junior: 'начинающий специалист',
  middle: 'специалист',
  senior: 'ведущий специалист',
  lead: 'руководитель группы',
  executive: 'руководитель направления',
  unknown: null,
}

const PARSER_LABELS: Record<string, string> = {
  docling: 'docling',
  builtin: 'встроенный разбор',
}

type Props = {
  resume: Resume
  facts: ResumeFacts
}

/** What was read from the resume: the role, the areas and the recognised skills. */
export function ResumeFactsView({ resume, facts }: Props) {
  const level = SENIORITY_LABELS[facts.seniority]
  return (
    <div>
      <p className="text-xs text-muted-foreground">
        {resume.file_format.toUpperCase()}
        {resume.parser && ` · ${PARSER_LABELS[resume.parser] ?? resume.parser}`} ·{' '}
        {facts.by_model ? 'разобрано языковой моделью' : 'разобрано по таблице направлений'}
      </p>
      <p className="mt-1.5 font-serif text-xl leading-snug font-semibold">{facts.headline}</p>
      {level && <p className="mt-0.5 text-sm text-muted-foreground">{level}</p>}
      {facts.summary && <p className="mt-3 text-sm text-foreground/90">{facts.summary}</p>}
      {facts.skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {facts.skills.map((skill) => (
            <Chip key={skill}>{skill}</Chip>
          ))}
        </div>
      )}
    </div>
  )
}
