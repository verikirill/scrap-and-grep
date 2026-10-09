import { toast as heroToast } from '@heroui/react'
import type { ReactNode } from 'react'

type Options = { description?: ReactNode }

/**
 * Notifications through HeroUI's toast queue, under the names the code calls:
 * a plain note, a success and an error.
 */
export const toast = Object.assign(
  (message: ReactNode, options?: Options) => heroToast(message, options),
  {
    success: (message: ReactNode, options?: Options) => heroToast.success(message, options),
    error: (message: ReactNode, options?: Options) => heroToast.danger(message, options),
  },
)
