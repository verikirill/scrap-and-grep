import { ListBox, Select } from '@heroui/react'
import clsx from 'clsx'

export type SelectOption = { value: string; label: string; disabled?: boolean }

// React Aria keys cannot be empty, so an option that means "none" travels
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
 * HeroUI's select with its own list. A native select opens the system's list,
 * which ignores the theme: white on Windows even in the dark one.
 */
export function SelectField({ value, onChange, options, label, className, disabled }: Props) {
  // The name carries the visible value too, so a voice command that reads the
  // field ("Безопасность") finds it: "Категория: Безопасность".
  const current = options.find((option) => option.value === value)?.label
  return (
    <Select
      aria-label={current ? `${label}: ${current}` : label}
      selectedKey={wrap(value)}
      onSelectionChange={(next) => {
        if (next !== null) onChange(String(next) === NONE ? '' : String(next))
      }}
      disabledKeys={options.filter((option) => option.disabled).map((option) => wrap(option.value))}
      isDisabled={disabled}
      className={clsx('w-full', className)}
    >
      <Select.Trigger>
        <Select.Value className="min-w-0 truncate" />
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox aria-label={label}>
          {options.map((option) => (
            <ListBox.Item key={option.value} id={wrap(option.value)} textValue={option.label}>
              {option.label}
              <ListBox.ItemIndicator />
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  )
}
