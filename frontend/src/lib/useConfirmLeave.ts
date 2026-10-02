import { useEffect } from 'react'

/**
 * Asks before unsaved work is left: on a link to another page of the app and
 * on closing or reloading the tab. The app's router has no navigation blocker
 * (that needs a data router), so links are caught before React sees them.
 * The browser's Back button is not asked about: only a data router can stop it.
 */
export function useConfirmLeave(isDirty: boolean, message: string): void {
  useEffect(() => {
    if (!isDirty) return
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null
      if (!(link instanceof HTMLAnchorElement) || link.target === '_blank') return
      const url = new URL(link.href, window.location.href)
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return
      if (!window.confirm(message)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault()
    // Capture on the document runs before the router's own click handler.
    document.addEventListener('click', onClick, true)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      document.removeEventListener('click', onClick, true)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [isDirty, message])
}
