import type { Me } from './api'

/** Who sees a section: everyone, whoever may run channels, a space's manager, or the administrator. */
export type Access = 'all' | 'publisher' | 'manager' | 'admin'

/**
 * What an account may open. A reader on their own runs channels too; people a
 * company added read, and its channels are the manager's. The company section
 * is the manager's and the administrator's: a reader starts a space from
 * the account page.
 */
export function navAccess(me: Me | null | undefined): Record<Access, boolean> {
  const isAdmin = Boolean(me?.is_admin && !me.is_demo)
  const role = me?.company?.role
  return {
    all: true,
    publisher: role !== 'member',
    manager: Boolean(me && !me.is_demo && (role === 'owner' || isAdmin)),
    admin: isAdmin,
  }
}
