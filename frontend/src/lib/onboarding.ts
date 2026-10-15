import type { Me } from './api'

/** Where the first-run introduction lives. */
export const ONBOARDING_PATH = '/start'

/**
 * A reader the introduction is offered to on its own: registered, and not yet
 * through it (finished or skipped). Guests start with example profiles and
 * never get it; anyone may still open it on demand from the account page.
 */
export function needsOnboarding(me: Me | null | undefined): boolean {
  return Boolean(me && !me.is_demo && me.onboarded_at === null)
}
