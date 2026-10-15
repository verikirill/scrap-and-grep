import type { Me } from '../../lib/api'
import { Tile } from './PreviewParts'
import type { Section } from './sections'
import { StepHeading } from './StepHeading'

/** One section of the app: what it is for, a few things it can do, and its picture. */
export function SectionStep({ section, me }: { section: Section; me?: Me | null }) {
  const { Preview } = section
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] items-center gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] md:gap-10">
      <div>
        <StepHeading kicker={`Раздел «${section.label}»`}>{section.title}</StepHeading>
        <p className="mt-3 text-[15px] text-pretty text-muted">{section.lead}</p>
        <ul className="mt-5 space-y-2.5">
          {section.points.map((point) => (
            <li key={point.text} className="flex items-start gap-3 text-sm">
              <Tile icon={point.icon} size={28} />
              <span className="min-w-0 pt-1 text-pretty">{point.text}</span>
            </li>
          ))}
        </ul>
      </div>
      <Preview me={me} />
    </div>
  )
}
