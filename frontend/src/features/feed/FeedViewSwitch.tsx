import { Segmented } from '../../components/Segmented'
import { ViewCards, ViewChat } from '../../components/icons'
import type { IconComponent } from '../../components/icons'
import type { FeedView } from '../../lib/api'
import { useUpdateSettings } from '../../lib/queries'
import { toast } from '../../lib/toast'

const VIEWS: readonly { value: FeedView; label: string; icon: IconComponent }[] = [
  { value: 'cards', label: 'Карточки', icon: ViewCards },
  { value: 'telegram', label: 'Как в Telegram', icon: ViewChat },
]

/**
 * How the feed looks, beside its tabs. Kept with the account, so every device
 * shows the same; the look changes at once and comes back if the server
 * refuses it. Where the row is narrow only the icons stay, with their names.
 */
export function FeedViewSwitch({ view }: { view: FeedView }) {
  const update = useUpdateSettings()
  const choose = (next: FeedView) => {
    if (next === view) return
    update.mutate(
      { feed_view: next },
      {
        onError: (error) =>
          toast.error('Вид ленты не сохранился', {
            description: error instanceof Error ? error.message : undefined,
          }),
      },
    )
  }
  return (
    <Segmented
      label="Вид ленты"
      value={view}
      options={VIEWS}
      onChange={choose}
      className="shrink-0"
      itemClassName="px-2 sm:px-2 @4xl:px-3"
      labelClassName="hidden @4xl:inline"
    />
  )
}
