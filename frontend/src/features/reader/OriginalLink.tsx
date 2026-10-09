import { ExternalLink } from '../../components/icons'
import { externalHref } from '../../lib/format'

type Props = {
  url: string
  title: string
  /** Opening the original counts as reading, like opening the article in the app. */
  onOpen?: () => void
}

/**
 * The article on its site, beside a title that opens it in the app. Shown on
 * hover where there is a pointer to hover with; always, and larger, on
 * touch screens.
 */
export function OriginalLink({ url, title, onOpen }: Props) {
  return (
    <a
      href={externalHref(url)}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onOpen}
      // The middle button opens a tab without a click event; the right one only a menu.
      onAuxClick={(event) => {
        if (event.button === 1) onOpen?.()
      }}
      aria-label={`«${title}» на сайте источника`}
      title="Открыть на сайте источника"
      className="transition-colors hover:bg-default/70 relative -my-2 grid size-10 shrink-0 place-items-center overflow-hidden rounded-full text-muted transition-opacity hover:text-foreground focus-visible:opacity-100 pointer-fine:-my-1 pointer-fine:size-8 pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100"
    >
      <ExternalLink size={15} />
    </a>
  )
}
