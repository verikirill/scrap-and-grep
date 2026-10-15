import type { ComponentType } from 'react'
import {
  Account,
  Bookmark,
  CircleCheck,
  Clapperboard,
  CompareArrows,
  DynamicFeed,
  EventRepeat,
  ExternalLink,
  EyeOff,
  FileUp,
  Hub,
  Newspaper,
  Rss,
  Schedule,
  Search,
  Send,
  SlidersHorizontal,
  Sparkles,
  Target,
  ThumbsUp,
  ViewChat,
  Palette,
  AutoAwesome,
  Eye,
  Users,
  ShieldCheck,
  RotateCcw,
} from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import type { Me } from '../../lib/api'
import { ComparePreview, DigestPreview, FeedPreview } from './previewsRead'
import { AccountPreview, ChannelsPreview, ProfilesPreview, SourcesPreview } from './previewsSetup'

export type Section = {
  key: string
  /** The section's name in the sidebar. */
  label: string
  icon: IconComponent
  title: string
  lead: string
  points: { icon: IconComponent; text: string }[]
  Preview: ComponentType<{ me?: Me | null }>
}

/** The sections of the app in the order of the sidebar, each told in a few lines. */
export const SECTIONS: readonly Section[] = [
  {
    key: 'digest',
    label: 'Дайджест',
    icon: Newspaper,
    title: 'Выпуск под вашу задачу',
    lead: 'Выберите профиль и период, от суток до месяца. Ассистент найдёт публикации, уберёт повторы и напишет выжимки со ссылками на источники.',
    points: [
      { icon: Target, text: 'Специалисту: матрица риска и план на смену' },
      { icon: Clapperboard, text: 'Короткое видео по выпуску с субтитрами' },
      { icon: Sparkles, text: '«Спросить выпуск»: ответы только по его записям' },
      { icon: EventRepeat, text: 'Выпуск может собираться сам по расписанию' },
    ],
    Preview: DigestPreview,
  },
  {
    key: 'feed',
    label: 'Для вас',
    icon: DynamicFeed,
    title: 'Лента, которая учится',
    lead: 'Публикации за две недели, подобранные по интересам, резюме и вашим отметкам. У каждой видно, почему она здесь.',
    points: [
      { icon: ThumbsUp, text: '«Больше такого» и «Меньше такого» меняют следующую подборку' },
      { icon: Bookmark, text: 'Нужное можно сохранить, лишнее скрыть' },
      { icon: ViewChat, text: 'Вид «Посты» показывает ленту как канал в Telegram' },
    ],
    Preview: FeedPreview,
  },
  {
    key: 'profiles',
    label: 'Интересы',
    icon: SlidersHorizontal,
    title: 'Профили интересов',
    lead: 'Профиль задаёт темы, ключевые слова и исключения. Профилей может быть несколько: для своей работы, для руководства, для соседнего отдела.',
    points: [
      {
        icon: AutoAwesome,
        text: '«Подстройка по отметкам» предлагает новые темы и поправляет их вес',
      },
      { icon: EyeOff, text: 'Лишние поля карточек и блоки выпуска можно скрыть' },
      { icon: Eye, text: 'Предпросмотр сразу показывает, что попадёт в выпуск' },
    ],
    Preview: ProfilesPreview,
  },
  {
    key: 'channels',
    label: 'Каналы',
    icon: Send,
    title: 'Свой канал в Telegram',
    lead: 'Подключите своего бота, и он сам будет публиковать новости в ваш канал по расписанию.',
    points: [
      { icon: Schedule, text: 'Каждые N минут или в заданное время, по выбранным дням' },
      { icon: Palette, text: 'Тон постов, ссылки и формат настраиваются для каждого канала' },
      { icon: CircleCheck, text: 'Можно публиковать только после вашей проверки' },
    ],
    Preview: ChannelsPreview,
  },
  {
    key: 'sources',
    label: 'Источники',
    icon: Rss,
    title: 'Откуда берутся новости',
    lead: 'Больше 100 RSS-лент, сайтов и Telegram-каналов по ИТ, ИБ и энергетике. Сервис опрашивает их каждые 15 минут.',
    points: [
      {
        icon: Search,
        text: 'Во вкладке «Публикации» поиск по всему собранному, в том числе по смыслу',
      },
      { icon: ExternalLink, text: 'Любую публикацию можно открыть в оригинале и сверить' },
      { icon: ShieldCheck, text: 'Видно, какие источники читаются, а какие давно молчат' },
    ],
    Preview: SourcesPreview,
  },
  {
    key: 'compare',
    label: 'Сравнение',
    icon: CompareArrows,
    title: 'Два выпуска рядом',
    lead: 'Выберите, что было и что стало: сервис покажет, что появилось, что ушло и как изменились оценки.',
    points: [
      { icon: SlidersHorizontal, text: 'Так видно, что изменила правка интересов' },
      { icon: RotateCcw, text: '«Сравнить с предыдущим» открывается прямо из выпуска' },
    ],
    Preview: ComparePreview,
  },
  {
    key: 'account',
    label: 'Аккаунт',
    icon: Account,
    title: 'Ваш аккаунт',
    lead: 'Аккаунт открывается по вашей картинке: внизу меню, а на телефоне вверху экрана. Там же можно пройти это знакомство ещё раз.',
    points: [
      { icon: Users, text: 'Девять пушистых картинок на выбор или своё фото' },
      {
        icon: FileUp,
        text: 'Резюме задаёт специализацию, лента учитывает её наравне с интересами',
      },
      { icon: Hub, text: 'Ключ MCP открывает ИИ-ассистенту вашу ленту, выпуски и интересы' },
    ],
    Preview: AccountPreview,
  },
]
