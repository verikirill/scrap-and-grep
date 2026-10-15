import { motion } from 'motion/react'
import { ArtTile } from '../../components/ArtTile'
import { BrandCat } from '../../components/BrandCat'
import { AutoAwesome, Target } from '../../components/icons'
import { Button } from '../../components/ui'
import { Tile } from './PreviewParts'
import { rise } from './motion'
import { SECTIONS } from './sections'
import { StepHeading } from './StepHeading'

const SETUP = [
  { key: 'profile', label: 'Ваш профиль', icon: Target },
  { key: 'digest', label: 'Первый выпуск', icon: AutoAwesome },
]

type Props = {
  name: string | undefined
  onStart: () => void
  onSetup: () => void
}

/** The greeting: what the service does and the map of the tour ahead. */
export function IntroStep({ name, onStart, onSetup }: Props) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] items-center gap-6 md:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] md:gap-10">
      <ArtTile className="order-first w-36 grid-cols-[minmax(0,1fr)] justify-self-center p-3 md:order-last md:w-64 md:p-5">
        <BrandCat size={232} className="max-w-full" />
      </ArtTile>
      <div>
        <StepHeading kicker="Знакомство">
          {name ? `Здравствуйте, ${name}` : 'Здравствуйте'}
        </StepHeading>
        <p className="mt-3 text-base text-pretty">
          Scrap&Grep читает больше 100 источников по ИТ, информационной безопасности и энергетике и
          собирает из них короткие выпуски под ваши задачи.
        </p>
        <p className="mt-2 text-sm text-pretty text-muted">
          Сначала коротко покажем разделы, потом настроим профиль интересов и соберём первый выпуск.
          Это займёт пару минут, а поменять всё можно позже.
        </p>

        <ol aria-label="Что покажем" className="mt-5 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {[...SECTIONS, ...SETUP].map((item, index) => (
            <motion.li
              key={item.key}
              {...rise(index * 0.5)}
              className={
                index < SECTIONS.length
                  ? 'flex min-w-0 items-center gap-2 rounded-xl bg-surface-secondary py-1.5 pr-2 pl-1.5 text-[13px]'
                  : 'flex min-w-0 items-center gap-2 rounded-xl bg-accent-soft py-1.5 pr-2 pl-1.5 text-[13px] font-medium text-accent-soft-foreground'
              }
            >
              <Tile icon={item.icon} size={24} />
              <span className="truncate">{item.label}</span>
            </motion.li>
          ))}
        </ol>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button variant="cta" className="w-full sm:w-auto" onClick={onStart}>
            Начать знакомство
          </Button>
          <Button variant="ghost" className="w-full sm:w-auto" onClick={onSetup}>
            Сразу к настройке
          </Button>
        </div>
      </div>
    </div>
  )
}
