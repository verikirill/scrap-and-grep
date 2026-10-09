import { RangeCalendar } from '@heroui/react'
import { CalendarDate } from '@internationalized/date'
import { I18nProvider } from 'react-aria-components'

/** A period picked in the calendar: both ends are days, the end is inclusive. */
export type DateRange = { from: Date; to?: Date }

type Props = {
  selected: DateRange | undefined
  onSelect: (range: DateRange | undefined) => void
  /** The earliest and the latest day that can be picked. */
  min: Date
  max: Date
  /** The month shown first. */
  defaultMonth?: Date
}

const toDay = (date: Date) =>
  new CalendarDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
const toDate = (day: CalendarDate) => new Date(day.year, day.month - 1, day.day)

/** A month of days on HeroUI's range calendar, in Russian, weeks from Monday. */
export function Calendar({ selected, onSelect, min, max, defaultMonth }: Props) {
  const value = selected?.to ? { start: toDay(selected.from), end: toDay(selected.to) } : null
  return (
    <I18nProvider locale="ru-RU">
      <RangeCalendar
        aria-label="Период выпуска"
        value={value}
        defaultFocusedValue={toDay(defaultMonth ?? max)}
        minValue={toDay(min)}
        maxValue={toDay(max)}
        onChange={(range) => {
          if (range) onSelect({ from: toDate(range.start), to: toDate(range.end) })
        }}
      >
        <RangeCalendar.Header>
          <RangeCalendar.Heading className="capitalize" />
          <RangeCalendar.NavButton slot="previous" />
          <RangeCalendar.NavButton slot="next" />
        </RangeCalendar.Header>
        <RangeCalendar.Grid>
          <RangeCalendar.GridHeader>
            {(day) => <RangeCalendar.HeaderCell>{day}</RangeCalendar.HeaderCell>}
          </RangeCalendar.GridHeader>
          <RangeCalendar.GridBody>
            {(date) => <RangeCalendar.Cell date={date} />}
          </RangeCalendar.GridBody>
        </RangeCalendar.Grid>
      </RangeCalendar>
    </I18nProvider>
  )
}
