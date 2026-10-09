import clsx from 'clsx'
import type { ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Class names joined, a later Tailwind utility winning over an earlier one of its kind. */
export function cn(...values: ClassValue[]): string {
  return twMerge(clsx(values))
}
