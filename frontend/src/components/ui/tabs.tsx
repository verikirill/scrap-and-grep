import { Tabs as HeroTabs } from '@heroui/react'
import clsx from 'clsx'
import type { ReactNode } from 'react'

/*
 * Tabs on HeroUI's, under the names the code calls: a list of triggers and a
 * panel for each, keyed by the same value.
 */

type TabsProps = {
  defaultValue: string
  className?: string
  children: ReactNode
}

export function Tabs({ defaultValue, className, children }: TabsProps) {
  return (
    <HeroTabs defaultSelectedKey={defaultValue} className={clsx('flex flex-col', className)}>
      {children}
    </HeroTabs>
  )
}

type ListProps = {
  className?: string
  /** "line" draws the triggers on one rule instead of a filled track. */
  variant?: 'default' | 'line'
  'aria-label'?: string
  children: ReactNode
}

export function TabsList({ className, variant = 'default', children, ...rest }: ListProps) {
  return (
    <HeroTabs.ListContainer className={clsx('max-w-full overflow-x-auto', className)}>
      <HeroTabs.List
        aria-label={rest['aria-label'] ?? 'Разделы'}
        className={clsx(variant === 'line' && 'bg-transparent')}
      >
        {children}
      </HeroTabs.List>
    </HeroTabs.ListContainer>
  )
}

export function TabsTrigger({
  value,
  className,
  children,
}: {
  value: string
  className?: string
  children: ReactNode
}) {
  return (
    <HeroTabs.Tab id={value} className={clsx('whitespace-nowrap', className)}>
      {children}
      <HeroTabs.Indicator />
    </HeroTabs.Tab>
  )
}

export function TabsContent({
  value,
  className,
  children,
}: {
  value: string
  className?: string
  children: ReactNode
}) {
  return (
    <HeroTabs.Panel id={value} className={className}>
      {children}
    </HeroTabs.Panel>
  )
}
