import clsx from 'clsx'
import { Eye, ImageOff } from 'lucide-react'
import { useState } from 'react'
import type { PostContent } from '../../lib/publishing'
import { PostHtml } from './PostHtml'

function Picture({ url }: { url: string }) {
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')
  if (state === 'failed') {
    return (
      <div className="grid h-40 place-items-center bg-black/5 text-xs text-[#707579] dark:bg-white/5 dark:text-[#7f91a4]">
        <span className="flex items-center gap-1.5">
          <ImageOff size={14} /> картинку не загрузить отсюда
        </span>
      </div>
    )
  }
  return (
    <div className={clsx('relative', state === 'loading' && 'skeleton h-48 rounded-none')}>
      <img
        src={url}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onLoad={() => setState('ready')}
        onError={() => setState('failed')}
        className={clsx(
          'block max-h-[420px] w-full object-cover transition-opacity duration-300',
          state === 'ready' ? 'opacity-100' : 'opacity-0',
        )}
      />
    </div>
  )
}

/**
 * A post the way a channel shows it: the channel name, the picture, the text
 * and the buttons under it. Drawn from the same content the bot sends.
 */
export function TelegramPreview({
  content,
  channel,
  className,
}: {
  content: PostContent
  channel: string
  className?: string
}) {
  const media = content.media[0]?.url ?? content.preview_url ?? null
  const caption = <PostHtml html={content.html} mode={content.format} />
  return (
    <div
      className={clsx(
        'rounded-[22px] bg-[#e4ecf2] p-3 dark:bg-[#0e1621]',
        // Telegram's wallpaper is busy; a flat tone keeps attention on the post.
        className,
      )}
    >
      <article className="max-w-[440px] overflow-hidden rounded-2xl bg-white text-[14.5px] leading-[1.45] text-[#000] shadow-sm dark:bg-[#182533] dark:text-[#f5f5f5]">
        <header className="px-3 pt-2 text-[14px] font-semibold text-[#3390ec] dark:text-[#6ab3f3]">
          {channel}
        </header>
        {content.caption_above_media && <div className="px-3 py-2">{caption}</div>}
        {media && (
          <div className="mt-2">
            {/* A new address starts over: one that failed must not mark the next as failed. */}
            <Picture key={media} url={media} />
          </div>
        )}
        {!content.caption_above_media && <div className="px-3 pt-2">{caption}</div>}
        <footer className="flex items-center justify-end gap-1 px-3 pb-1.5 text-[11px] text-[#707579] dark:text-[#7f91a4]">
          <Eye size={12} /> 1 · {content.format === 'rich' ? 'rich' : 'пост'}
        </footer>
        {content.buttons.length > 0 && (
          <div className="grid gap-1 p-1">
            {content.buttons.map((button) => (
              <span
                key={button.url + button.text}
                className="rounded-lg bg-[#3390ec]/10 py-2 text-center text-[13.5px] font-medium text-[#3390ec] dark:bg-white/10 dark:text-[#6ab3f3]"
              >
                {button.text}
              </span>
            ))}
          </div>
        )}
      </article>
    </div>
  )
}
