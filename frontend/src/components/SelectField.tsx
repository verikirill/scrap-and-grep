import { Select as SelectPrimitive } from 'radix-ui'
import { cn } from 'cn'
import { CheckIcon, ChevronDownIcon } from './icons'
import { INPUT_CLASS } from './tokens'

export type SelectOption = { value: string; label: string; disabled?: boolean }

// Radix keeps "" for "nothing chosen", so an option that means "none" travels
// under this name and comes back to the caller as "".
const NONE = '__none__'
const wrap = (value: string) => (value === '' ? NONE : value)

type Props = {
  value: string
  onChange: (value: string) => void
  options: readonly SelectOption[]
  /** The field's name: a screen reader hears it on the field and on its list. */
  label: string
  className?: string
  disabled?: boolean
}

/**
 * The outlined field of the forms with its own list. A native select opens the
 * system's list, which ignores the theme: white on Windows even in the dark one.
 */
export function SelectField({ value, onChange, options, label, className, disabled }: Props) {
  // The name carries the visible value too, so a voice command that reads the
  // field ("Безопасность") finds it: "Категория: Безопасность".
  const current = options.find((option) => option.value === value)?.label
  return (
    <SelectPrimitive.Root
      value={wrap(value)}
      onValueChange={(next) => onChange(next === NONE ? '' : next)}
      disabled={disabled}
    >
      <SelectPrimitive.Trigger
        aria-label={current ? `${label}: ${current}` : label}
        className={cn(
          INPUT_CLASS,
          'group flex cursor-pointer items-center justify-between gap-2 text-left',
          'data-[state=open]:border-primary data-[state=open]:ring-1 data-[state=open]:ring-primary',
          'focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary',
          className,
        )}
      >
        <span className="min-w-0 truncate">
          <SelectPrimitive.Value />
        </span>
        <SelectPrimitive.Icon asChild>
          <ChevronDownIcon
            aria-hidden
            className="size-4 shrink-0 text-on-surface-variant transition-transform duration-200 group-data-[state=open]:rotate-180"
          />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          aria-label={label}
          position="popper"
          sideOffset={6}
          collisionPadding={12}
          className={cn(
            'z-50 min-w-(--radix-select-trigger-width) overflow-hidden rounded-2xl border border-outline-variant',
            'bg-popover p-1.5 text-popover-foreground shadow-lg',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
            'data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1',
          )}
        >
          <SelectPrimitive.Viewport className="max-h-[min(20rem,var(--radix-select-content-available-height))]">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={wrap(option.value)}
                disabled={option.disabled}
                className={cn(
                  'relative flex min-h-10 cursor-pointer items-center rounded-xl py-2 pr-9 pl-3 text-sm',
                  'outline-none select-none data-highlighted:bg-on-surface/8',
                  'data-[state=checked]:font-medium data-[state=checked]:text-primary',
                  'data-disabled:pointer-events-none data-disabled:opacity-40',
                )}
              >
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-3 flex items-center">
                  <CheckIcon aria-hidden className="size-4" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
