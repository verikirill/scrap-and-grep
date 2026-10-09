import clsx from 'clsx'
import { Card, ErrorNote } from '../../components/ui'
import type { FeedView, Me } from '../../lib/api'
import { useUpdateSettings } from '../../lib/queries'

const VIEWS: { value: FeedView; label: string; hint: string }[] = [
  {
    value: 'cards',
    label: 'Карточки',
    hint: 'Все причины подбора и оценка видны сразу, текст плотнее',
  },
  {
    value: 'telegram',
    label: 'Как в Telegram',
    hint: 'Посты с картинкой статьи и аватаром источника, причины по нажатию',
  },
]

/** A sketch of each look, so the choice does not need the words. */
function Sketch({ view }: { view: FeedView }) {
  if (view === 'cards') {
    return (
      <div aria-hidden className="space-y-1.5 rounded-xl bg-surface-secondary p-2.5">
        {[0, 1].map((card) => (
          <div key={card} className="space-y-1 rounded-lg border border-separator bg-surface p-2">
            <div className="h-1.5 w-1/3 rounded-full bg-separator" />
            <div className="h-2 w-4/5 rounded-full bg-foreground/40" />
            <div className="h-1.5 w-full rounded-full bg-separator" />
            <div className="flex gap-1 pt-0.5">
              <div className="h-2 w-8 rounded-full bg-accent/25" />
              <div className="h-2 w-10 rounded-full bg-accent/15" />
            </div>
          </div>
        ))}
      </div>
    )
  }
  return (
    <div aria-hidden className="chat-wallpaper space-y-1.5 rounded-xl p-2.5">
      {[0, 1].map((post) => (
        <div key={post} className="flex items-end gap-1.5">
          <div className="size-4 shrink-0 rounded-full bg-[var(--tag-teal)]" />
          <div className="flex-1 overflow-hidden rounded-lg rounded-bl-sm bg-background dark:bg-surface-tertiary">
            {post === 0 && <div className="h-7 bg-accent/20" />}
            <div className="space-y-1 p-1.5">
              <div className="h-1.5 w-1/3 rounded-full bg-[var(--on-tag-teal)] opacity-60" />
              <div className="h-2 w-4/5 rounded-full bg-foreground/40" />
              <div className="flex gap-1 pt-0.5">
                <div className="h-2 w-4 rounded-full bg-accent/20" />
                <div className="h-2 w-4 rounded-full bg-accent/20" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

/** How the feed looks; kept with the account, so every device shows the same. */
export function FeedViewSetting({ me }: { me: Me }) {
  const update = useUpdateSettings()
  return (
    <Card className="p-5 sm:p-6">
      <fieldset>
        <legend className="text-base font-semibold">Вид ленты</legend>
        <p className="mt-1 text-sm text-muted">
          Состав и порядок статей не меняются, переключается только оформление.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {VIEWS.map((view) => {
            const isChosen = me.feed_view === view.value
            return (
              <label
                key={view.value}
                className={clsx(
                  'block cursor-pointer rounded-2xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent',
                  isChosen
                    ? 'border-accent bg-accent-soft/40'
                    : 'border-separator hover:border-border',
                )}
              >
                <input
                  type="radio"
                  name="feed-view"
                  value={view.value}
                  checked={isChosen}
                  onChange={() => update.mutate({ feed_view: view.value })}
                  className="sr-only"
                />
                <Sketch view={view.value} />
                <span className="mt-3 flex items-center gap-2 text-sm font-medium">
                  <span
                    aria-hidden
                    className={clsx(
                      'grid size-4 place-items-center rounded-full border-2',
                      isChosen ? 'border-accent' : 'border-border',
                    )}
                  >
                    {isChosen && <span className="size-2 rounded-full bg-accent" />}
                  </span>
                  {view.label}
                </span>
                <span className="mt-1 block text-xs text-muted">{view.hint}</span>
              </label>
            )
          })}
        </div>
      </fieldset>
      <div className="mt-3">
        <ErrorNote error={update.error} />
      </div>
    </Card>
  )
}
