import { BriefcaseBusiness, Compass, Heart, Rss, Target, Users } from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import type { FeedItem, FeedReason } from '../../lib/api'

export const REASON_ICONS: Record<FeedReason['kind'], IconComponent> = {
  interest: Target,
  resume: BriefcaseBusiness,
  learned: Heart,
  collab: Users,
  source: Rss,
  explore: Compass,
}

export const reasonIcon = (kind: FeedReason['kind']): IconComponent => REASON_ICONS[kind] ?? Target

/** The score has parts worth explaining: not for a saved item or a newest-first pick. */
export const hasBreakdown = (item: FeedItem) => Object.keys(item.parts).length > 0 && !item.explore
